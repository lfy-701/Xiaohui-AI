"""健康检查与连通性探测（不消耗 DeepSeek 额度）。"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.schemas import DeepSeekHealth, HealthResponse, PingResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="服务健康检查")
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    started_at = getattr(request.app.state, "started_at", time.monotonic())

    return HealthResponse(
        status="ok" if settings.has_api_key else "degraded",
        service=settings.app_name,
        version=settings.version,
        uptime_s=round(time.monotonic() - started_at, 1),
        deepseek=DeepSeekHealth(
            configured=settings.has_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            thinking_enabled=settings.thinking_enabled,
            reasoning_effort=settings.reasoning_effort,
            request_timeout_s=settings.request_timeout_s,
            total_timeout_s=settings.total_timeout_s,
        ),
    )


@router.get("/api/v1/ping", response_model=PingResponse, summary="低开销 RTT 探测")
async def ping() -> PingResponse:
    now = datetime.now(timezone.utc)
    return PingResponse(
        server_time=now.isoformat(timespec="milliseconds"),
        server_time_ms=int(now.timestamp() * 1000),
    )
