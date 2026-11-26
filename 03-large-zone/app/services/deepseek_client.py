"""DeepSeek API 客户端。

只封装阶段 2 需要的能力：Chat Completions 与模型列表。
所有请求参数严格对齐官方文档（2026-11）：

- base_url: https://api.deepseek.com
- POST /chat/completions，模型 deepseek-flash / deepseek-v4-pro
- 思考模式：{"thinking": {"type": "enabled"|"disabled"}}，默认开启，因此这里显式关闭
- 思考模式下 temperature 不生效，故仅在非思考模式传 temperature
- 错误码：400/401/402/408/413/422/429/500/503/504

异常一律转换为 AppError，向上层暴露稳定的 code。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, NoReturn, Sequence

import openai
from openai import AsyncOpenAI

from app.config import Settings
from app.errors import ConfigurationError, ContentFilteredError, UpstreamError

logger = logging.getLogger(__name__)

Message = dict[str, str]


@dataclass(slots=True)
class ChatResult:
    reply: str
    model: str
    finish_reason: str | None = None
    reasoning: str | None = None
    response_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0


def _usage_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}

    cached = getattr(usage, "prompt_cache_hit_tokens", None)
    if cached is None:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) or 0

    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        "cached_tokens": int(cached or 0),
    }


def _upstream_message(exc: openai.APIError) -> str:
    """提取上游错误文案，截断后用于日志/响应，避免把整段 HTML 透传给设备。"""
    raw = getattr(exc, "message", None) or str(exc)
    raw = " ".join(str(raw).split())
    return raw[:300]


def _retry_after(exc: openai.APIStatusError) -> int | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after")
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


class DeepSeekClient:
    """异步客户端，进程内复用连接池。"""

    def __init__(self, settings: Settings, http_client: Any | None = None) -> None:
        self._settings = settings
        self._client: AsyncOpenAI | None = None

        # 没有 Key 时不构造 SDK，避免启动即崩；健康检查会报告未配置。
        if settings.has_api_key:
            self._client = AsyncOpenAI(
                api_key=""
                base_url=settings.deepseek_base_url,
                timeout=settings.request_timeout_s,
                max_retries=settings.max_retries,
                http_client=http_client,
            )

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _require_client(self) -> AsyncOpenAI:
        if self._client is None:
            raise ConfigurationError(
                "服务端未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek。"
                "请把 server/.env.example 复制为 server/.env 并填写密钥，然后重启服务。"
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()

    def _map_error(self, exc: Exception) -> NoReturn:
        """把 openai SDK 异常映射为带稳定 code 的 AppError。"""
        if isinstance(exc, openai.APITimeoutError):
            raise UpstreamError(
                "DeepSeek 请求超时，请稍后重试", status_code=504, code="upstream_timeout"
            ) from exc

        if isinstance(exc, openai.AuthenticationError):
            raise UpstreamError(
                "DeepSeek 拒绝鉴权（401），请检查服务端 DEEPSEEK_API_KEY 是否正确",
                status_code=502,
                code="upstream_auth_failed",
            ) from exc

        if isinstance(exc, openai.PermissionDeniedError):
            raise UpstreamError(
                "DeepSeek 拒绝访问（403），请检查账号权限或实名状态",
                status_code=502,
                code="upstream_permission_denied",
            ) from exc

        if isinstance(exc, openai.RateLimitError):
            raise UpstreamError(
                "DeepSeek 触发限流（429），请退避后重试",
                status_code=429,
                code="upstream_rate_limited",
                retry_after=_retry_after(exc),
            ) from exc

        if isinstance(exc, openai.BadRequestError):
            raise UpstreamError(
                f"DeepSeek 拒绝了请求参数（400）：{_upstream_message(exc)}",
                status_code=502,
                code="upstream_bad_request",
            ) from exc

        if isinstance(exc, openai.APIStatusError):
            status = exc.status_code
            if status == 402:
                raise UpstreamError(
                    "DeepSeek 账户余额不足（402），请充值后重试",
                    status_code=502,
                    code="upstream_insufficient_balance",
                ) from exc
            if status in (500, 503):
                raise UpstreamError(
                    f"DeepSeek 服务暂时不可用（{status}），请稍后重试",
                    status_code=503,
                    code="upstream_unavailable",
                ) from exc
            raise UpstreamError(
                f"DeepSeek 返回异常状态 {status}：{_upstream_message(exc)}",
                status_code=502,
                code="upstream_status_error",
            ) from exc

        if isinstance(exc, openai.APIConnectionError):
            raise UpstreamError(
                "无法连接 DeepSeek，请检查服务器网络、DNS 或代理设置",
                status_code=503,
                code="upstream_unreachable",
            ) from exc

        raise UpstreamError(
            f"调用 DeepSeek 时发生未知错误：{type(exc).__name__}",
            status_code=502,
            code="upstream_unknown_error",
        ) from exc

    async def _guarded(self, awaitable: Any) -> Any:
        """统一处理总超时（含 SDK 内部重试）与异常映射。"""
        try:
            async with asyncio.timeout(self._settings.total_timeout_s):
                return await awaitable
        except TimeoutError as exc:  # 总超时，SDK 的重试也一并取消
            raise UpstreamError(
                f"DeepSeek 请求超过 {self._settings.total_timeout_s:g} 秒总超时",
                status_code=504,
                code="upstream_timeout",
            ) from exc
        except openai.APIError as exc:
            self._map_error(exc)
        except Exception as exc:  # httpx 层异常等
            raise UpstreamError(
                f"调用 DeepSeek 失败：{type(exc).__name__}",
                status_code=503,
                code="upstream_unreachable",
            ) from exc

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        user_id: str | None = None,
    ) -> ChatResult:
        client = self._require_client()
        settings = self._settings

        use_thinking = settings.thinking_enabled if thinking is None else thinking
        effort = reasoning_effort or settings.reasoning_effort

        # 深度思考时推理内容也占输出 token，默认给更高预算
        if max_tokens is not None:
            token_limit = max_tokens
        elif use_thinking:
            token_limit = settings.max_tokens_thinking
        else:
            token_limit = settings.max_tokens

        extra_body: dict[str, Any] = {
            "thinking": {"type": "enabled" if use_thinking else "disabled"}
        }
        if user_id:
            # 官方支持 user_id 做 KV Cache / 调度隔离（放在 extra_body 里传给 OpenAI SDK）
            extra_body["user_id"] = user_id

        params: dict[str, Any] = {
            "model": settings.deepseek_model,
            "messages": list(messages),
            "max_tokens": token_limit,
            "stream": False,
            "extra_body": extra_body,
        }
        if use_thinking:
            params["reasoning_effort"] = effort
        else:
            # 思考模式下 temperature 不生效，非思考模式才传
            params["temperature"] = settings.temperature if temperature is None else temperature

        started = time.perf_counter()
        response = await self._guarded(client.chat.completions.create(**params))
        latency_ms = int((time.perf_counter() - started) * 1000)

        if not getattr(response, "choices", None):
            raise UpstreamError("DeepSeek 返回了空的 choices", status_code=502, code="empty_choices")

        choice = response.choices[0]
        message = choice.message
        content = (getattr(message, "content", None) or "").strip()
        finish_reason = getattr(choice, "finish_reason", None)

        if not content:
            if finish_reason == "content_filter":
                raise ContentFilteredError("回复被 DeepSeek 内容安全策略拦截")
            raise UpstreamError(
                f"DeepSeek 返回空内容（finish_reason={finish_reason}）",
                status_code=502,
                code="empty_reply",
            )

        return ChatResult(
            reply=content,
            model=getattr(response, "model", None) or settings.deepseek_model,
            finish_reason=finish_reason,
            reasoning=getattr(message, "reasoning_content", None),
            response_id=getattr(response, "id", None),
            usage=_usage_dict(getattr(response, "usage", None)),
            latency_ms=latency_ms,
        )

    async def chat_stream(
        self,
        messages: Sequence[Message],
        *,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        user_id: str | None = None,
    ):
        """流式对话：逐段产出文本增量（async generator）。

        与 chat() 的区别只有 stream=True；不做工具循环（工具意图由语音侧走本地通道）。
        调用方（语音服务）拿到第一句就该开始 TTS，不必等整段写完。
        """
        client = self._require_client()
        settings = self._settings

        use_thinking = settings.thinking_enabled if thinking is None else thinking
        effort = reasoning_effort or settings.reasoning_effort

        if max_tokens is not None:
            token_limit = max_tokens
        elif use_thinking:
            token_limit = settings.max_tokens_thinking
        else:
            token_limit = settings.max_tokens

        extra_body: dict[str, Any] = {
            "thinking": {"type": "enabled" if use_thinking else "disabled"}
        }
        if user_id:
            extra_body["user_id"] = user_id

        params: dict[str, Any] = {
            "model": settings.deepseek_model,
            "messages": list(messages),
            "max_tokens": token_limit,
            "stream": True,
            "extra_body": extra_body,
        }
        if use_thinking:
            params["reasoning_effort"] = effort
        else:
            params["temperature"] = settings.temperature if temperature is None else temperature

        stream = await client.chat.completions.create(**params)
        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            piece = getattr(delta, "content", None) if delta is not None else None
            if piece:
                yield piece

    async def list_models(self) -> list[dict[str, Any]]:
        """GET /models，用于验证 Key 与网络是否可用。"""
        client = self._require_client()
        page = await self._guarded(client.models.list())
        return [
            {
                "id": getattr(model, "id", None),
                "owned_by": getattr(model, "owned_by", None),
                "context_window": getattr(model, "context_window", None),
                "max_output_tokens": getattr(model, "max_output_tokens", None),
            }
            for model in getattr(page, "data", [])
        ]


    async def call_with_tools(self, messages, tools, max_tokens=None, max_rounds=3):
        """带工具调用：返回与 chat() 相同结构的结果对象。"""
        import json as _json

        core = self._require_client()

        for _ in range(max(1, int(max_rounds))):
            resp = await core.chat.completions.create(
                model=self._settings.deepseek_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=max_tokens or self._settings.max_tokens,
                temperature=self._settings.temperature,
            )
            msg = resp.choices[0].message
            calls = getattr(msg, "tool_calls", None)
            if not calls:
                text = (msg.content or "").strip()
                from app.services.deepseek_client import ChatResult  # noqa: F401
                return _LocalResult(text=text, tokens=(resp.usage.total_tokens if resp.usage else 0))

            # 把模型的工具调用意图写回历史
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in calls
                ],
            })

            from app.services.tools import execute_tool

            for tc in calls:
                try:
                    out = execute_tool(tc.function.name, tc.function.arguments)
                except Exception as e:
                    out = f"工具失败: {e}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(out)[:1500],
                })

        return _LocalResult(text="抱歉，我这边处理有点绕，你能再说一次吗？", tokens=0)



class _LocalResult:
    """call_with_tools 的返回结构，字段与 chat() 结果保持一致。"""

    def __init__(self, text: str, tokens: int = 0):
        self.reply = text
        self.text = text
        self.reasoning = ""
        self.model = "deepseek-tools"
        self.finish_reason = "stop"
        self.latency_ms = 0
        self.response_id = None
        self.usage = {"total_tokens": tokens}
