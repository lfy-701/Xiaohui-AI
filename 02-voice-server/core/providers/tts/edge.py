import asyncio
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import edge_tts
from datetime import datetime
from core.providers.tts.base import TTSProviderBase
from core.utils.voice_settings import load as load_voice_settings

from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# ---------------------------------------------------------------- 挂起保护
# Edge 是外部服务，2026-11-26 17:08 实测单句从 2.0s 恶化到 7~17s（TLS 只有 0.3s，
# 说明是服务端合成排队，不是网络）。而 edge_tts 调用本身没有超时——
# 一旦服务端卡住，语音服务会一直干等（日志里出现过「9 个字合成 24.4 秒」）。
#
# 这里加四道保护：
#   1. 单次合成硬超时（默认 12s）——用线程池跑，超时取消 future 立即返回。
#      取 12s 而不是 5s：Edge 波动到 7~17s 时，5s 会让每句都失败、设备直接没声音，
#      宁可慢一次也要出声；健康时本来 2s 就返回，这个上限不产生成本。
#   2. 默认只尝试 1 次，避免「多次超时 × 每次 12s」叠加成长尾。
#   3. 熔断：一旦超时，冷却期内（默认 60s）不再调用 Edge，直接用缓存短句。
#   4. 彻底不可用时用缓存短句兜底；预热度不足时由 tts_warmup 后台重试补缓存。
_TTS_TIMEOUT_S = max(2.0, float(os.getenv("TTS_TIMEOUT_S", "12")))
# 尝试 2 次：Edge 存在「瞬时 No audio was received」抖动（实测第 1 次失败、第 2 次成功），
# 只试 1 次会直接兜底成固定短句、内容就错了。超时不做重试（见下方 break），所以不会拉长尾。
_TTS_ATTEMPTS = max(1, int(os.getenv("TTS_ATTEMPTS", "2")))
_BREAKER_COOLDOWN_S = max(10.0, float(os.getenv("TTS_BREAKER_S", "60")))
_FALLBACK_TEXT = (os.getenv("TTS_FALLBACK_TEXT", "嗯，我在呢。") or "").strip()

# 熔断状态：Edge 超时后在这之前不再尝试真实合成
_BREAKER_UNTIL = 0.0
# 被超时放弃、但仍在后台线程里挂着的合成任务数。
# 这些线程最终会因 socket 超时自己结束，但如果一直累积就说明 Edge 服务端挂了，
# 这时要把冷却时间拉长，避免继续制造挂起线程（实测会推高进程内存）。
_ABANDONED = 0
_ABANDONED_LIMIT = max(4, int(os.getenv("TTS_ABANDON_LIMIT", "8")))
# 熔断期间每这么久放行一次探测（自愈用）
_PROBE_AFTER_S = max(5.0, float(os.getenv("TTS_PROBE_S", "20")))
_LAST_PROBE = 0.0


def breaker_state() -> dict:
    """供排查：当前熔断状态、剩余冷却时间与挂起线程数。"""
    left = max(0.0, _BREAKER_UNTIL - time.time())
    return {"open": left > 0, "cooldown_left_s": round(left, 1),
            "abandoned": _ABANDONED}


def _note_abandoned() -> None:
    global _ABANDONED
    _ABANDONED += 1
    if _ABANDONED >= _ABANDONED_LIMIT:
        logger.bind(tag=TAG).warning(
            f"已累计 {_ABANDONED} 个挂起的合成线程，延长熔断到 300s（Edge 服务端疑似不可用）"
        )
        _open_breaker(f"累计挂起 {_ABANDONED} 个线程", cooldown=300.0)


def _open_breaker(reason: str, cooldown: float | None = None) -> None:
    global _BREAKER_UNTIL
    cool = _BREAKER_COOLDOWN_S if cooldown is None else cooldown
    _BREAKER_UNTIL = time.time() + cool
    logger.bind(tag=TAG).warning(
        f"Edge TTS 进入熔断（{reason}），接下来 {cool:.0f}s 内直接用缓存短句"
    )


def _breaker_open() -> bool:
    """冷却期内为 True；但每隔 _PROBE_AFTER_S 放行一次探测，让服务能自愈。

    没有探测的话，一旦进入 60s 熔断，期间所有句子都会走兜底/失败；
    而 Edge 往往是抖动几秒就恢复，干等 60s 体验很差。
    """
    global _LAST_PROBE
    now = time.time()
    if now >= _BREAKER_UNTIL:
        return False
    if now - _LAST_PROBE >= _PROBE_AFTER_S:
        _LAST_PROBE = now
        logger.bind(tag=TAG).info("Edge 熔断中，放行一次探测请求")
        return False
    return True


class TTSUnavailable(Exception):
    """Edge 合成彻底不可用（超时/失败耗尽重试），base 层据此不再重试。"""

# ---------------------------------------------------------------- 合成缓存
# Edge TTS 每合成一句都要新建一条 WebSocket，光握手就 0.6~0.8s，
# 整句固定开销 2.0~2.5s（12 字和 60 字差不多）。而小慧说的很多话是重复的
# ——动作确认、问候、天气模板、固定短句——这些完全没必要每次重合成。
#
# 缓存键 = 音色|语速|音调|文本，所以控制台改了音色/语速会自动失效；
# 只缓存短文本（默认 ≤40 字），避免长篇回答把内存吃满。
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = max(0, int(os.getenv("TTS_CACHE_MAX", "300")))
_CACHE_MAX_CHARS = max(0, int(os.getenv("TTS_CACHE_MAX_CHARS", "40")))


def _cache_key(text: str, voice: str, rate: str, pitch: str) -> str:
    return f"{voice}|{rate}|{pitch}|{text}"


def _cache_get(key: str):
    with _CACHE_LOCK:
        return _CACHE.get(key)


def _cache_put(key: str, data: bytes) -> None:
    if not _CACHE_MAX or len(data) > 512 * 1024:
        return
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            # 简单淘汰：清掉最早的一半，避免维护 LRU 的复杂度
            for k in list(_CACHE.keys())[: max(1, _CACHE_MAX // 2)]:
                _CACHE.pop(k, None)
        _CACHE[key] = data


def cache_stats() -> dict:
    with _CACHE_LOCK:
        return {"entries": len(_CACHE), "max": _CACHE_MAX,
                "bytes": sum(len(v) for v in _CACHE.values())}


def clear_cache() -> int:
    with _CACHE_LOCK:
        n = len(_CACHE)
        _CACHE.clear()
        return n


async def _synth_bytes(text: str, voice: str, rate: str, pitch: str) -> bytes:
    """纯合成，不查缓存（在独立线程的事件循环里跑，见 _synth_bounded）。"""
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    buf = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    return bytes(buf)


def _synth_sync(text: str, voice: str, rate: str, pitch: str) -> bytes:
    """线程内入口：自己开一个事件循环跑合成。"""
    return asyncio.run(_synth_bytes(text, voice, rate, pitch))


# 线程池：把合成放到独立线程，超时时取消 future 能立即返回。
# 实测（2026-11-26 17:11）asyncio.wait_for 直接包 edge_tts 时，
# 超时并不会及时生效（压到 0.6s 时实际等了 20.1s），所以必须走线程池。
_EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv("TTS_MAX_WORKERS", "4")),
                               thread_name_prefix="edge-tts")


async def _synth_bounded(text: str, voice: str, rate: str, pitch: str) -> bytes:
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(_EXECUTOR, _synth_sync, text, voice, rate, pitch)
    return await asyncio.wait_for(fut, timeout=_TTS_TIMEOUT_S)


async def synthesize_bytes(text: str, voice: str, rate: str, pitch: str,
                           use_cache: bool = True) -> bytes:
    """带缓存 + 硬超时 + 熔断 + 兜底的合成（预热脚本也走这里）。"""
    key = _cache_key(text, voice, rate, pitch)
    cacheable = bool(_CACHE_MAX and _CACHE_MAX_CHARS and len(text) <= _CACHE_MAX_CHARS)
    if use_cache and cacheable:
        hit = _cache_get(key)
        if hit:
            return hit

    def _fallback() -> bytes | None:
        """只用缓存里的兜底短句，绝不再发起网络请求。"""
        if not _FALLBACK_TEXT or _FALLBACK_TEXT == text:
            return None
        return _cache_get(_cache_key(_FALLBACK_TEXT, voice, rate, pitch))

    if _breaker_open():
        fb = _fallback()
        if fb:
            logger.bind(tag=TAG).info(f"Edge 熔断中，用缓存短句回复：{text[:20]}")
            return fb
        raise TTSUnavailable("Edge TTS 熔断中且无可用缓存")

    last_error: Exception | None = None
    for attempt in range(1, _TTS_ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            data = await _synth_bounded(text, voice, rate, pitch)
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - started
            last_error = asyncio.TimeoutError()
            logger.bind(tag=TAG).warning(
                f"Edge 合成超时（{elapsed:.1f}s / 上限 {_TTS_TIMEOUT_S:.0f}s，"
                f"第 {attempt}/{_TTS_ATTEMPTS} 次，{len(text)} 字）：{text[:20]}"
            )
            _open_breaker(f"合成超时 {elapsed:.1f}s")
            _note_abandoned()          # 该次合成的线程会被放弃，但仍在后台挂着
            break                      # 超时不再重试，直接走兜底
        except Exception as exc:
            last_error = exc
            logger.bind(tag=TAG).warning(
                f"Edge 合成失败（第 {attempt}/{_TTS_ATTEMPTS} 次，{len(text)} 字）：{exc}"
            )
            continue
        if data:
            if use_cache and cacheable:
                _cache_put(key, data)
            return data

    fb = _fallback()
    if fb:
        logger.bind(tag=TAG).warning(
            f"Edge 不可用，改用缓存兜底短句「{_FALLBACK_TEXT}」，原文：{text[:20]}"
        )
        return fb

    raise TTSUnavailable(f"Edge TTS 不可用：{type(last_error).__name__ if last_error else 'unknown'}")



class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        if config.get("private_voice"):
            self.voice = config.get("private_voice")
        else:
            self.voice = config.get("voice")
        # 控制台「设定 → 音色」的运行时覆盖（每通连接建立时读取）
        try:
            runtime_voice = load_voice_settings().get("voice")
            if runtime_voice:
                self.voice = runtime_voice
        except Exception:
            pass
        self.audio_file_type = config.get("format", "mp3")

    def generate_filename(self, extension=".mp3"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        try:
            # 语速 / 音调由控制台「语音设置」控制，每次合成时读取，改完即生效
            vs = load_voice_settings()
            # 音色也支持热切换：控制台保存后下一句就用新音色
            _v = (vs.get("voice") or "").strip()
            if _v:
                self.voice = _v
            data = await synthesize_bytes(
                text,
                self.voice,
                vs.get("rate") or "+0%",
                vs.get("pitch_hz") or "+0Hz",
            )
            if not data:
                return None
            if output_file:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "wb") as f:
                    f.write(data)
            else:
                return data
        except TTSUnavailable:
            # 不要包成普通 Exception：base 层靠类型名判断"别重试"，
            # 一旦被包住就会重试 5 次（实测日志出现「语音生成失败5次」并拖慢整轮）
            raise
        except Exception as e:
            error_msg = f"Edge TTS请求失败: {e}"
            raise Exception(error_msg)  # 抛出异常，让调用方捕获
