"""请求上下文中间件：注入 X-Request-ID、耗时，并打一条精简访问日志。

使用纯 ASGI 实现（不用 BaseHTTPMiddleware），避免将来加 SSE 流式语音时被缓冲。
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders

from app.metrics import RequestMetrics

logger = logging.getLogger("app.access")

SKIP_LOG_PATHS = {"/health", "/favicon.ico", "/docs", "/redoc", "/openapi.json"}


class RequestContextMiddleware:
    def __init__(self, app, metrics: RequestMetrics | None = None) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or uuid.uuid4().hex[:16]

        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            elapsed_ms = (time.perf_counter() - started) * 1000
            if self.metrics is not None:
                self.metrics.record(
                    method=scope.get("method", "?"),
                    path=path,
                    status=status_code,
                    latency_ms=int(elapsed_ms),
                    request_id=request_id,
                )
            if path not in SKIP_LOG_PATHS:
                logger.info(
                    "%s %s -> %s (%.1f ms) rid=%s",
                    scope.get("method"),
                    path,
                    status_code,
                    elapsed_ms,
                    request_id,
                )
