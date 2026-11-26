"""统一错误模型。

所有对外错误都返回同一结构，ESP32 端只需解析一种格式：

    {"error": {"code": "...", "message": "...", "request_id": "..."}}

code 是稳定的机器可读标识，message 是给人看的中文说明。
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """应用层可预期错误，会被全局处理器转换为 JSON。"""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.retry_after = retry_after
        self.details = details or {}

    def to_payload(self, request_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if request_id:
            body["request_id"] = request_id
        if self.details:
            body["details"] = self.details
        return {"error": body}


class ConfigurationError(AppError):
    """服务端缺少必要配置（例如没有 API Key），属于运维问题。"""

    status_code = 503
    code = "deepseek_not_configured"


class UpstreamError(AppError):
    """DeepSeek 侧失败：鉴权、限流、超时、网络不可达等。"""

    status_code = 502
    code = "upstream_error"


class ContentFilteredError(AppError):
    """模型输出被安全策略拦截。"""

    status_code = 422
    code = "content_filtered"
