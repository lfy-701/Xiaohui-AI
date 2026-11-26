import os
import time
import httpx
import openai
from openai.types import CompletionUsage
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.llm.base import LLMProviderBase

TAG = __name__
logger = setup_logging()


# 这些意图必须走工具通道：宁可慢 2 秒，也不能让模型编造
STRICT_TOOL_HINTS = (
    "天气", "气温", "温度", "下雨", "下雪", "冷不冷", "热不热", "穿什么",
    "空气质量", "预报", "台风", "暴雨",
    "新闻", "头条", "热搜", "时事", "最近发生",
    "搜索", "搜一下", "查一下", "查查", "限行", "路况", "多少钱", "汇率",
)

_TOOL_HINTS = (
    "天气", "气温", "温度", "下雨", "会不会冷", "穿衣", "空气", "预报",
    "新闻", "头条", "热搜", "时事",
    "搜索", "搜一下", "查一下", "查查", "限行", "路况",
    "提醒我", "闹钟", "计时", "倒计时",
    "音乐", "歌曲", "放首", "放一", "来首", "放个歌", "听歌",
    "站起来", "坐下", "趴下", "跳舞", "左转", "右转", "往前走", "往后退",
    "起身", "摇尾巴", "摇摇头", "开灯", "关灯", "灯珠",
)


def _last_user_text(dialogue):
    try:
        for m in reversed(dialogue or []):
            if isinstance(m, dict) and m.get("role") == "user":
                return str(m.get("content") or "")
    except Exception:
        pass
    return ""


def _tool_mode_for(dialogue):
    """需要工具/实时信息时返回 None（走完整通道），闲聊返回 "off"。"""
    txt = _last_user_text(dialogue)
    if not txt:
        return "off"
    if any(k in txt for k in STRICT_TOOL_HINTS):
        return None
    return None if any(k in txt for k in _TOOL_HINTS) else "off"


def _with_date(dialogue):
    """在系统提示里补当前日期，模型就不会乱猜今天几号。"""
    try:
        import datetime

        now = datetime.datetime.now()
        hint = "当前时间是{}年{}月{}日 星期{} {}:{}。涉及日期时间一律以此为准。".format(
            now.year, now.month, now.day, "一二三四五六日"[now.weekday()],
            str(now.hour).zfill(2), str(now.minute).zfill(2),
        )
        out = []
        injected = False
        for m in dialogue or []:
            if isinstance(m, dict) and m.get("role") == "system" and not injected:
                out.append({"role": "system", "content": hint + "\n" + str(m.get("content") or "")})
                injected = True
            else:
                out.append(m)
        if not injected:
            out.insert(0, {"role": "system", "content": hint})
        return out
    except Exception:
        return dialogue


# ---------------------------------------------------------------- 混合路由
_ZONE_DEEP_WORDS = (
    "为什么", "怎么理解", "解释", "分析", "原理", "推导", "证明",
    "作业", "数学题", "解题", "作文", "写好", "区别", "比较",
    "详细说说", "深入", "科普", "原理是什么", "怎么做",
)


def _zone_route(dialogue) -> tuple:
    """返回 (是否走专区, 最后一句用户文本)。"""
    import os as _os

    last = ""
    history = []
    try:
        for m in dialogue or []:
            role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
            content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
            if not content:
                continue
            if role == "user":
                last = str(content)
            if role in ("user", "assistant"):
                history.append({"role": role, "content": str(content)})
    except Exception:
        return False, ""

    if _os.getenv("ZONE_HYBRID", "1") != "1":
        return False, last

    text = last.strip()
    if not text:
        return False, last

    # 「全部走云端大模型」（ZONE_ALL_CLOUD=1，默认开）：
    # 不再把问候/工具意图分流给本地小模型，一律交给专区（云端 DeepSeek API）。
    # 需要恢复原来的分流策略时，把环境变量 ZONE_ALL_CLOUD 设为 0。
    if _os.getenv("ZONE_ALL_CLOUD", "1") != "1":
        # 唤醒问候/寒暄原本走本地：专区首响应 3~5 秒，设备会因等待而停止聆听
        _greet = ("你好", "您好", "嘿", "嗨", "在吗", "早上好", "晚上好", "晚安", "早啊")
        if len(text) <= 10 and any(g in text for g in _greet):
            return False, last

        # 需要工具的问题原本交给本地模型（它有 MCP 工具）
        _TOOL_HINTS = (
            "搜索", "搜一下", "查一下", "查查", "限行", "路况",
            "知识库", "课本", "教材", "第几单元", "提醒", "闹钟", "计时",
            "灯", "灯珠", "坐下", "趴下", "站起来", "跳舞", "前进", "后退",
            "左转", "右转", "摇尾巴", "摇头", "音量",
        )
        if any(k in text for k in _TOOL_HINTS):
            return False, last

    # 模式：all = 全部走专区；hybrid = 只有难题走专区
    mode = _os.getenv("ZONE_MODE", "all").strip().lower()
    if mode == "all":
        return True, last

    try:
        min_len = int(_os.getenv("ZONE_MIN_LEN", "18"))
    except Exception:
        min_len = 18

    hit_word = any(w in text for w in _ZONE_DEEP_WORDS)
    if hit_word or len(text) >= min_len:
        return True, last
    return False, last


def _ask_zone(question: str, history: list, system_extra: str = "") -> str:
    """调大模型专区，返回纯文本回复；失败返回空串。

    专区偶尔会返回 200 但 reply 为空（上游 DeepSeek 超时/被截断），
    以前这种要干等到超时才回退，体感就是「反应特别慢」。
    这里改成本地快速判定 + 立刻重试一次。
    """
    import os as _os
    import time as _t

    import httpx as _hx

    base = _os.getenv("ZONE_URL", "http://127.0.0.1:8013").rstrip("/")
    try:
        timeout = float(_os.getenv("ZONE_TIMEOUT", "8"))
    except Exception:
        timeout = 8.0
    timeout = min(timeout, 8.0)

    # 故事类放宽长度，其余保持短答（降低延迟）
    _story_keys = ("故事", "讲个", "讲一", "童话", "睡前", "小说", "编一个", "编个")
    if any(k in question for k in _story_keys):
        _max_tokens = int(_os.getenv("ZONE_MAX_TOKENS_STORY", "350"))
    else:
        _max_tokens = int(_os.getenv("ZONE_MAX_TOKENS", "90"))
    _q = question
    if any(k in question for k in _story_keys):
        _q = question + "（请把故事完整讲完，120 字左右，讲完整）"
    payload = {
        "message": _q,
        "history": history[-6:],
        "max_tokens": _max_tokens,
    }
    # 长期记忆：专区用自己的人设，所以把「记得用户什么」显式透传过去
    if system_extra:
        payload["system_extra"] = system_extra

    for attempt in (1, 2):
        t0 = _t.time()
        try:
            with _hx.Client(timeout=timeout) as c:
                r = c.post(base + "/api/v1/chat", json=payload)
            cost = _t.time() - t0
            if r.status_code != 200:
                logger.bind(tag=TAG).warning(
                    f"专区返回 {r.status_code}（{cost:.1f}s）: {r.text[:100]}"
                )
                continue
            data = r.json()
            ans = (data.get("reply") or "").strip()
            if ans:
                return ans
            logger.bind(tag=TAG).warning(
                f"专区空回复（{cost:.1f}s，model={data.get('model')}），重试一次"
            )
        except Exception as e:
            logger.bind(tag=TAG).warning(f"专区调用失败（{_t.time()-t0:.1f}s）: {e}")
    return ""


def _ask_zone_stream(question: str, history: list, system_extra: str = ""):
    """从专区 SSE 拿文本增量（生成器）。

    与 _ask_zone 的区别：不等整段写完，边收边 yield，让上层按标点切句后
    第一句就能进 TTS —— 这是「故事类 5 秒才开始出声」的主要解法。
    """
    import json as _json

    import httpx as _hx

    base = os.getenv("ZONE_URL", "http://127.0.0.1:8013").rstrip("/")
    # 流式不能沿用整段那套 8s 上限：长回答的总时长本来就超过 8s，
    # 用 8s 会把正常请求判成超时并回退整段（实测出现「专区流式失败，回退整段: timed out」）。
    # 这里只把「单次读间隔」放宽到 25s，连接仍然 5s 超时。
    try:
        _read_timeout = float(os.getenv("ZONE_STREAM_TIMEOUT", "25"))
    except Exception:
        _read_timeout = 25.0
    _timeout = _hx.Timeout(connect=5.0, read=_read_timeout, write=10.0, pool=5.0)

    _story_keys = ("故事", "讲个", "讲一", "童话", "睡前", "小说", "编一个", "编个")
    if any(k in question for k in _story_keys):
        _max_tokens = int(os.getenv("ZONE_MAX_TOKENS_STORY", "350"))
        _q = question + "（请把故事完整讲完，120 字左右，讲完整）"
    else:
        _max_tokens = int(os.getenv("ZONE_MAX_TOKENS", "90"))
        _q = question

    payload = {"message": _q, "history": history[-6:], "max_tokens": _max_tokens}
    if system_extra:
        payload["system_extra"] = system_extra

    with _hx.Client(timeout=_timeout) as c:
        with c.stream("POST", base + "/api/v1/chat/stream", json=payload) as r:
            if r.status_code != 200:
                raise RuntimeError(f"专区流式返回 {r.status_code}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    obj = _json.loads(body)
                except Exception:
                    continue
                if obj.get("error"):
                    raise RuntimeError(str(obj["error"]))
                piece = obj.get("delta") or ""
                if piece:
                    yield piece


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        # 控制台「设定 → 模型与记忆」的运行时覆盖（每通连接建立时读取）
        try:
            from core.utils.voice_settings import load as _load_voice_settings

            runtime_model = _load_voice_settings().get("model")
            if runtime_model:
                self.model_name = runtime_model
        except Exception:
            pass
        self.api_key = config.get("api_key")
        if "base_url" in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")
        # 增加timeout的配置项，单位为秒
        timeout = config.get("timeout", 300)
        self.timeout = int(timeout) if timeout else 300

        param_defaults = {
            "max_tokens": (500, int),
            "temperature": (0.7, lambda x: round(float(x), 1)),
            "top_p": (1.0, lambda x: round(float(x), 1)),
            "frequency_penalty": (0, lambda x: round(float(x), 1)),
        }

        for param, (default, converter) in param_defaults.items():
            value = config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else default,
                )
            except (ValueError, TypeError):
                setattr(self, param, default)

        logger.debug(
            f"意图识别参数初始化: {self.temperature}, {self.max_tokens}, {self.top_p}, {self.frequency_penalty}"
        )

        model_key_msg = check_model_key("LLM", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)
        # 语音场景走快速通道：跳过 MCP 工具 schema 注入（模型服务支持 x-tool-mode 头）
        # 注意：本地兜底模型经常整台不可达。timeout 原来取配置的 300 秒，
        # 连不上时要干等很久才回退；语音对话里 15 秒已经足够，超时就换说法。
        _local_timeout = min(float(self.timeout or 15), 15.0)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url,
                                    timeout=httpx.Timeout(_local_timeout))



    def response(self, session_id, dialogue, **kwargs):
        # 混合路由：难题交给大模型专区
        try:
            _use_zone, _q = _zone_route(dialogue)
            if _use_zone:
                _hist = []
                try:
                    for m in dialogue or []:
                        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
                        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
                        if role in ("user", "assistant") and content:
                            _hist.append({"role": role, "content": str(content)})
                except Exception:
                    _hist = []
                # 优先走专区流式：首句一到就交给 TTS，不必等整段（V1.2 阶段四）
                if (os.getenv("ZONE_STREAM", "1") or "1").strip() == "1":
                    _yielded = False
                    try:
                        for _piece in _ask_zone_stream(
                            _q, _hist, kwargs.get("system_extra", "") or ""
                        ):
                            _yielded = True
                            yield _piece
                        if _yielded:
                            logger.bind(tag=TAG).info("混合路由：专区流式回答完成")
                            return
                    except Exception as e:
                        logger.bind(tag=TAG).warning(f"专区流式失败，回退整段: {e}")
                        if _yielded:
                            return  # 已经吐过内容，再回退整段会重复
                _ans = _ask_zone(_q, _hist, kwargs.get("system_extra", "") or "")
                if _ans:
                    logger.bind(tag=TAG).info(f"混合路由：大模型专区回答 {len(_ans)} 字")
                    yield _ans
                    return
                logger.bind(tag=TAG).warning("专区整段重试后仍无回应")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"混合路由异常: {e}")

        # 「只走云端大模型」（ZONE_ALL_CLOUD=1）：不再回退本地小模型。
        # 本地模型（<本地模型服务器IP>:8000）经常不可达，回退过去只会多等一轮再报错，
        # 不如直接给一句兜底话术，保证设备能出声、能继续听。
        if (os.getenv("ZONE_ALL_CLOUD", "1") or "1").strip() == "1":
            logger.bind(tag=TAG).warning("已启用 ZONE_ALL_CLOUD，跳过本地模型，使用兜底话术")
            yield "我这会儿网有点卡，你稍等一下再跟我说一遍好吗？"
            return

        # 模型支持热切换：控制台保存后下一次请求就用新模型
        try:
            from core.utils.voice_settings import load as _load_rt2
            _m = (_load_rt2().get("model") or "").strip()
            if _m:
                self.model_name = _m
        except Exception:
            pass
        # 上游重启或长连接失效时会断开；未产出任何内容前重试一次，
        # 否则设备会一直停在「说话中」状态。
        for attempt in range(2):
            yielded = False
            try:
                _mode = _tool_mode_for(dialogue)
                _extra = {"x-tool-mode": _mode} if _mode else None
                responses = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=_with_date(dialogue),
                    stream=True,
                    extra_headers=_extra,
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    temperature=kwargs.get("temperature", self.temperature),
                    top_p=kwargs.get("top_p", self.top_p),
                    frequency_penalty=kwargs.get(
                        "frequency_penalty", self.frequency_penalty
                    ),
                )

                is_active = True
                for chunk in responses:
                    try:
                        delta = (
                            chunk.choices[0].delta
                            if getattr(chunk, "choices", None)
                            else None
                        )
                        content = delta.content if hasattr(delta, "content") else ""
                    except IndexError:
                        content = ""
                    if content:
                        if "<think>" in content:
                            is_active = False
                            content = content.split("<think>")[0]
                        if "</think>" in content:
                            is_active = True
                            content = content.split("</think>")[-1]
                        if is_active:
                            yielded = True
                            yield content
                return

            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Error in response generation (attempt {attempt + 1}): {e}"
                )
                if yielded or attempt == 1:
                    return
                time.sleep(0.6)

    def response_with_functions(self, session_id, dialogue, functions=None):
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name, messages=dialogue, stream=True, tools=functions
            )

            for chunk in stream:
                # 检查是否存在有效的choice且content不为空
                if getattr(chunk, "choices", None):
                    yield chunk.choices[0].delta.content, chunk.choices[
                        0
                    ].delta.tool_calls
                # 存在 CompletionUsage 消息时，生成 Token 消耗 log
                elif isinstance(getattr(chunk, "usage", None), CompletionUsage):
                    usage_info = getattr(chunk, "usage", None)
                    logger.bind(tag=TAG).info(
                        f"Token 消耗：输入 {getattr(usage_info, 'prompt_tokens', '未知')}，"
                        f"输出 {getattr(usage_info, 'completion_tokens', '未知')}，"
                        f"共计 {getattr(usage_info, 'total_tokens', '未知')}"
                    )

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in function call streaming: {e}")
            yield f"【OpenAI服务响应异常: {e}】", None
