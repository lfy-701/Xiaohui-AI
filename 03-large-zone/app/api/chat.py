"""阶段 2 核心接口：文字对话。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.deps import get_deepseek_client
from app.schemas import ChatRequest, ChatResponse, Usage


class _SkipTools(Exception):
    pass
from app.services.conversation import build_messages
from app.services.fast_answers import fast_answer, now_context
from app.services.tools import TOOLS_SPEC, execute_tool
from app.services.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat/stream", summary="文字对话·SSE 流式版（首句优先）")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    client: DeepSeekClient = Depends(get_deepseek_client),
):
    """SSE 流式对话：逐段吐出文本增量，调用方拿到第一句就能开始 TTS。

    保留 /api/v1/chat 不动；本端点不做工具循环（工具意图由语音侧本地通道处理）。
    事件格式：`data: {"delta": "..."}` … 末尾 `data: [DONE]`；异常时 `data: {"error": "..."}`。
    """
    import json as _json
    import time as _time

    from fastapi.responses import StreamingResponse

    settings = request.app.state.settings

    def _sse(obj) -> str:
        return "data: " + _json.dumps(obj, ensure_ascii=False) + "\n\n"

    async def _gen():
        started = _time.perf_counter()
        try:
            fast = fast_answer(payload.message, getattr(settings, "default_city", "东莞"))
        except Exception:
            fast = None
        if fast:
            answer, source = fast
            yield _sse({"delta": answer, "model": "fast-" + source})
            yield "data: [DONE]\n\n"
            return

        messages = build_messages(settings, payload.message, payload.history)
        try:
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = messages[0]["content"] + now_context()
                _extra = (payload.system_extra or "").strip()
                if _extra:
                    messages[0]["content"] = messages[0]["content"] + "\n\n" + _extra
        except Exception:
            pass

        try:
            async for piece in client.chat_stream(
                messages,
                max_tokens=payload.max_tokens,
                user_id=payload.device_id,
            ):
                yield _sse({"delta": piece})
        except Exception as e:
            logger.warning("stream 失败: %s", e)
            yield _sse({"error": str(e)})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="文字对话（DeepSeek Chat Completions）",
    description=(
        "接收一句话（文字或 ASR 结果），返回可直接送 TTS 的简短回复。"
        "服务端无状态：历史对话由客户端通过 history 字段提供，服务端会再次裁剪。"
    ),
    responses={
        429: {"description": "DeepSeek 限流"},
        502: {"description": "DeepSeek 鉴权/余额/参数异常"},
        503: {"description": "未配置 API Key 或 DeepSeek 不可达"},
        504: {"description": "DeepSeek 超时"},
    },
)
async def chat(
    payload: ChatRequest,
    request: Request,
    client: DeepSeekClient = Depends(get_deepseek_client),
) -> ChatResponse:
    settings = request.app.state.settings

    # 1) 确定性回答（日期/天气）：不调用 DeepSeek，省额度也更快
    fast = fast_answer(payload.message, getattr(settings, "default_city", "东莞"))
    if fast:
        answer, source = fast
        logger.info("快速回答命中: %s", source)
        return ChatResponse(
            reply=answer,
            model="fast-" + source,
            finish_reason="stop",
            thinking=False,
            latency_ms=0,
            usage=Usage(),
        )

    # 2) 注入当前时间（不修改 settings，避免只读对象报错）
    messages = build_messages(settings, payload.message, payload.history)
    try:
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = messages[0]["content"] + now_context()
            # 调用方（语音设备）带来的长期记忆，拼在人设后面
            _extra = (payload.system_extra or "").strip()
            if _extra:
                messages[0]["content"] = messages[0]["content"] + "\n\n" + _extra
    except Exception:
        pass

    thinking = settings.thinking_enabled if payload.thinking is None else payload.thinking
    effort = payload.reasoning_effort or settings.reasoning_effort

    # 简单闲聊直接回答：跳过工具决策，省一次 API 往返
    _TOOL_WORDS = ("新闻", "天气", "几号", "星期", "气温", "温度", "搜", "查")
    _text = (payload.message or "").strip()
    SIMPLE_CHAT = len(_text) <= 14 and not any(w in _text for w in _TOOL_WORDS)

    result = None
    if SIMPLE_CHAT:
        try:
            result = await client.chat(
                messages,
                thinking=thinking,
                reasoning_effort=payload.reasoning_effort,
                max_tokens=payload.max_tokens,
                user_id=payload.device_id,
            )
        except Exception as _e:
            logger.warning("简单模式失败，改走工具循环: %s", _e)
            result = None
    try:
        if result is not None:
            raise _SkipTools()
        result = await client.call_with_tools(
            messages,
            tools=TOOLS_SPEC,
            max_tokens=payload.max_tokens,
            max_rounds=3,
        )
    except Exception as _e:
        logger.warning("工具循环失败，退回普通对话: %s", _e)
        result = None

    if result is None:
        result = await client.chat(
            messages,
            thinking=thinking,
            reasoning_effort=payload.reasoning_effort,
            max_tokens=payload.max_tokens,
            user_id=payload.device_id,
        )

    reasoning: str | None = None
    reasoning_truncated = False
    if thinking and payload.include_reasoning and result.reasoning:
        reasoning = result.reasoning.strip()
        if len(reasoning) > settings.max_reasoning_chars:
            reasoning = reasoning[: settings.max_reasoning_chars] + "…"
            reasoning_truncated = True

    logger.info(
        "chat ok device=%s thinking=%s effort=%s in_msgs=%d out_chars=%d reasoning_chars=%d "
        "latency_ms=%d tokens=%d",
        payload.device_id or "-",
        thinking,
        effort if thinking else "-",
        len(messages),
        len(result.reply),
        len(reasoning) if reasoning else 0,
        result.latency_ms,
        result.usage.get("total_tokens", 0),
    )

    return ChatResponse(
        reply=result.reply,
        model=result.model,
        finish_reason=result.finish_reason,
        thinking=thinking,
        reasoning_effort=effort if thinking else None,
        reasoning=reasoning,
        reasoning_truncated=reasoning_truncated,
        latency_ms=result.latency_ms,
        usage=Usage(**result.usage),
        request_id=result.response_id,
    )
