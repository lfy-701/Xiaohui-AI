"""TTS 启动预热。

背景（2026-11-26 实测）：
    Edge TTS 在新进程里的**第一次**合成要 13.5 秒，之后每句稳定 2.0~2.5 秒。
    语音服务每次重启，用户说的第一句话都要吃掉这 13 秒，体感就是「怎么这么慢」。
    原因在 Edge 侧（服务端/连接预热），本地无法消除，只能提前付掉这笔钱。

做法：
    服务起来后在后台线程里先合成一句短话（结果顺手进 edge.py 的合成缓存），
    再把「动作确认语」这类固定短句预合成进缓存——这些句子每轮都完全一样，
    命中缓存后合成耗时≈0，直接省掉 2 秒。

开关：
    TTS_WARMUP=0        关闭整个预热
    TTS_PREFILL=0       只预热，不预合成固定短句
    TTS_PREFILL_LIMIT=N 最多预合成多少句（默认 20）
"""

from __future__ import annotations

import asyncio
import os
import threading
import time

from config.logger import setup_logging

TAG = "tts_warmup"
logger = setup_logging()

_ENABLED = os.getenv("TTS_WARMUP", "1").strip().lower() not in ("0", "false", "off", "no")
_PREFILL_ENABLED = os.getenv("TTS_PREFILL", "1").strip().lower() not in ("0", "false", "off", "no")
_PREFILL_LIMIT = max(0, int(os.getenv("TTS_PREFILL_LIMIT", "20")))

_started = False
_lock = threading.Lock()

# Edge 服务端会阵发性劣化（2026-11-26 17:xx 实测单句从 2s 恶化到 7~17s）。
# 预热一次失败就放弃的话，缓存会一直是空的，后面每一句都要等 Edge。
# 所以这里做成「失败后按间隔重试，直到成功或达到上限」。
_WARM_RETRY_S = max(10.0, float(os.getenv("TTS_WARM_RETRY_S", "90")))
_WARM_MAX_ATTEMPTS = max(1, int(os.getenv("TTS_WARM_MAX_ATTEMPTS", "3")))


def _prefill_texts() -> list[str]:
    """要预合成的固定短句：问候语 + 动作确认语 + 几句最常见的口头确认。"""
    out: list[str] = ["你好。", "嗯，我在呢。", "我在听，你说。"]
    try:
        from core.utils.console_actions import ACTION_REPLIES

        out.extend(ACTION_REPLIES.values())
    except Exception:
        pass
    out.extend([
        "好，我在。",
        "抱歉，我没听清，你再说一遍？",
        "这个我还不知道，等会儿再问我一次？",
        "好，知道了。",
    ])
    # 去重 + 保持顺序 + 限长
    seen = set()
    uniq = []
    for t in out:
        t = (t or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq[:_PREFILL_LIMIT]


async def _warm_once(text: str, voice: str, rate: str, pitch: str) -> float:
    from core.providers.tts import edge as edge_provider

    started = time.perf_counter()
    data = await edge_provider.synthesize_bytes(text, voice, rate, pitch)
    return time.perf_counter() - started if data else -1.0


def _run() -> None:
    # 等服务初始化完（配置/日志/端口都在跑）
    time.sleep(2.0)
    try:
        from core.utils.voice_settings import load as load_voice_settings

        vs = load_voice_settings()
        voice = (vs.get("voice") or "zh-CN-XiaoxiaoNeural").strip()
        rate = vs.get("rate") or "+0%"
        pitch = vs.get("pitch_hz") or "+0Hz"
    except Exception:
        voice, rate, pitch = "zh-CN-XiaoxiaoNeural", "+0%", "+0Hz"

    warm_cost = -1.0
    # 先把「兜底短句」合成进缓存：即使后面一句话都合成失败，
    # 至少还有一句能出声（实测 18:04 那轮 Edge 熔断 + 缓存空 = 整轮没声音）。
    try:
        fb = (os.getenv("TTS_FALLBACK_TEXT", "嗯，我在呢。") or "").strip()
        if fb:
            asyncio.run(_warm_once(fb, voice, rate, pitch))
    except Exception:
        pass

    for attempt in range(1, _WARM_MAX_ATTEMPTS + 1):
        try:
            cost = asyncio.run(_warm_once("你好。", voice, rate, pitch))
        except Exception as e:
            cost = -1.0
            logger.bind(tag=TAG).warning(f"TTS 预热异常（第 {attempt} 次）：{e}")
        if cost >= 0:
            warm_cost = cost
            logger.bind(tag=TAG).info(f"TTS 预热完成：{cost:.1f}s（第 {attempt} 次尝试）")
            break
        if attempt < _WARM_MAX_ATTEMPTS:
            logger.bind(tag=TAG).info(
                f"TTS 预热未成功（第 {attempt}/{_WARM_MAX_ATTEMPTS} 次），"
                f"{_WARM_RETRY_S:.0f}s 后重试——Edge 服务端可能正在劣化"
            )
            time.sleep(_WARM_RETRY_S)

    if warm_cost < 0:
        logger.bind(tag=TAG).error(
            f"TTS 预热尝试 {_WARM_MAX_ATTEMPTS} 次仍未成功，短句缓存为空；"
            "后续每句都会受 Edge 延迟影响，请检查网络或考虑本地 TTS 兜底"
        )
        return

    if not _PREFILL_ENABLED or _PREFILL_LIMIT <= 0:
        return

    texts = _prefill_texts()
    done = 0
    started = time.perf_counter()
    skipped = 0
    for text in texts:
        # Edge 一进入熔断就停止预合成：继续跑只会不停制造挂起线程、把进程内存撑大
        try:
            from core.providers.tts.edge import breaker_state

            if breaker_state().get("open"):
                skipped = len(texts) - done
                logger.bind(tag=TAG).warning(
                    f"Edge 处于熔断，停止预合成（已完成 {done} 句，跳过 {skipped} 句）"
                )
                break
        except Exception:
            pass
        try:
            cost = asyncio.run(_warm_once(text, voice, rate, pitch))
            if cost >= 0:
                done += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
        time.sleep(0.05)
    try:
        from core.providers.tts.edge import cache_stats

        stats = cache_stats()
        logger.bind(tag=TAG).info(
            f"TTS 固定短句预合成：{done}/{len(texts)} 句（跳过 {skipped}），"
            f"耗时 {time.perf_counter() - started:.1f}s，"
            f"缓存 {stats['entries']} 条 / {stats['bytes'] // 1024}KB"
        )
    except Exception:
        pass


def start() -> bool:
    """后台启动预热（幂等）。"""
    global _started
    if not _ENABLED:
        logger.bind(tag=TAG).info("TTS 预热已关闭（TTS_WARMUP=0）")
        return False
    with _lock:
        if _started:
            return False
        _started = True
    t = threading.Thread(target=_run, name="tts-warmup", daemon=True)
    t.start()
    return True
