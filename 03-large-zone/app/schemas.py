"""HTTP 请求 / 响应模型（Pydantic v2）。

字段上限同时是成本保护：ESP32 端出错时不会把超大文本打进 DeepSeek。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "message": "小慧，今天有点累，陪我聊两句吧",
                    "device_id": "dog-001",
                    "history": [],
                },
                {
                    "message": "小慧，帮我认真想一下周末去哪儿玩",
                    "thinking": True,
                    "reasoning_effort": "high",
                    "include_reasoning": True,
                },
            ]
        },
    )

    message: str = Field(min_length=1, max_length=2000, description="本轮用户输入（ASR 结果或文字）")
    system_extra: str = Field(
        default="",
        max_length=4000,
        description="调用方追加的系统提示（如长期记忆），拼在服务端人设之后",
    )
    device_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="设备标识，用于 DeepSeek user_id 隔离与日志追踪",
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=40,
        description="由客户端维护的历史对话；服务端会再次裁剪",
    )
    thinking: bool | None = Field(
        default=None,
        description="是否启用深度思考；为空时使用服务端默认（关闭）",
    )
    reasoning_effort: Literal["low", "high", "max"] | None = Field(
        default=None,
        description="深度思考强度，仅在 thinking=true 时生效；为空时用服务端默认",
    )
    include_reasoning: bool = Field(
        default=False,
        description="是否在响应中返回思考过程（默认不返回，省流量）",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=16,
        le=4096,
        description="本轮回复 token 上限；深度思考未指定时用服务端更高的默认值",
    )


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class ChatResponse(BaseModel):
    reply: str = Field(description="模型回复，可直接送 TTS")
    model: str
    finish_reason: str | None = None
    thinking: bool = Field(description="本轮实际是否启用思考模式")
    reasoning_effort: str | None = Field(default=None, description="本轮实际使用的思考强度")
    reasoning: str | None = Field(default=None, description="思考过程，仅在 include_reasoning=true 时返回")
    reasoning_truncated: bool = Field(default=False, description="思考过程是否因长度上限被截断")
    latency_ms: int = Field(description="服务端到 DeepSeek 的往返耗时")
    usage: Usage = Field(default_factory=Usage)
    request_id: str | None = Field(default=None, description="DeepSeek 返回的请求 ID，用于对账")


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DeepSeekHealth(BaseModel):
    configured: bool
    model: str
    base_url: str
    thinking_enabled: bool
    reasoning_effort: str
    request_timeout_s: float
    total_timeout_s: float


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    uptime_s: float
    deepseek: DeepSeekHealth


class PingResponse(BaseModel):
    status: Literal["ok"] = "ok"
    server_time: str
    server_time_ms: int


class ConsoleConfig(BaseModel):
    model: str
    base_url: str
    thinking_enabled: bool
    reasoning_effort: str
    max_tokens: int
    max_tokens_thinking: int
    max_reasoning_chars: int
    temperature: float
    request_timeout_s: float
    total_timeout_s: float
    max_retries: int
    api_key_configured: bool
    console_token_configured: bool


class ConsoleStats(BaseModel):
    total_requests: int
    error_requests: int
    avg_latency_ms: int
    max_latency_ms: int
    sample_size: int


class ConsoleRequestRecord(BaseModel):
    ts: str
    method: str
    path: str
    status: int
    latency_ms: int
    request_id: str


class ConsoleOverview(BaseModel):
    service: str
    version: str
    status: Literal["ok", "degraded"]
    uptime_s: float
    config: ConsoleConfig
    stats: ConsoleStats
    recent: list[ConsoleRequestRecord]
