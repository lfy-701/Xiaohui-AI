"""控制台：单页 HTML + 只读概览接口。

安全默认：
- 配置了 CONSOLE_TOKEN 时，所有控制台接口必须带 X-Console-Token；
- 未配置时只允许本机（127.0.0.1/::1）访问，云端必须显式配置令牌。
- 概览不返回密钥，也不返回对话正文。
"""

from __future__ import annotations

import hmac
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.config import Settings
from app.deps import get_metrics, get_settings
from app.errors import AppError
from app.metrics import RequestMetrics
from app.schemas import (
    ConsoleConfig,
    ConsoleOverview,
    ConsoleRequestRecord,
    ConsoleStats,
)

CONSOLE_HTML = Path(__file__).resolve().parent.parent / "web" / "console.html"

# TestClient 的 client.host 固定为 testclient，仅用于本地测试
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

router = APIRouter(tags=["console"])


def require_console_access(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    provided = request.headers.get("x-console-token", "")
    if settings.console_token:
        if not hmac.compare_digest(provided, settings.console_token):
            raise AppError(
                "控制台令牌缺失或错误",
                status_code=401,
                code="console_auth_required",
            )
        return

    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        raise AppError(
            "未配置 CONSOLE_TOKEN，控制台仅允许本机访问；云端部署请设置该环境变量",
            status_code=401,
            code="console_auth_required",
        )


@router.get("/console", response_class=HTMLResponse, include_in_schema=False)
async def console_page() -> HTMLResponse:
    if not CONSOLE_HTML.exists():
        return HTMLResponse("<h1>console.html 缺失</h1>", status_code=500)
    return HTMLResponse(
        CONSOLE_HTML.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/api/v1/console/overview",
    response_model=ConsoleOverview,
    dependencies=[Depends(require_console_access)],
    summary="控制台概览（配置 + 指标 + 最近请求）",
)
async def overview(
    request: Request,
    settings: Settings = Depends(get_settings),
    metrics: RequestMetrics = Depends(get_metrics),
) -> ConsoleOverview:
    started_at = getattr(request.app.state, "started_at", time.monotonic())
    stats = metrics.stats()

    return ConsoleOverview(
        service=settings.app_name,
        version=settings.version,
        status="ok" if settings.has_api_key else "degraded",
        uptime_s=round(time.monotonic() - started_at, 1),
        config=ConsoleConfig(
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            thinking_enabled=settings.thinking_enabled,
            reasoning_effort=settings.reasoning_effort,
            max_tokens=settings.max_tokens,
            max_tokens_thinking=settings.max_tokens_thinking,
            max_reasoning_chars=settings.max_reasoning_chars,
            temperature=settings.temperature,
            request_timeout_s=settings.request_timeout_s,
            total_timeout_s=settings.total_timeout_s,
            max_retries=settings.max_retries,
            api_key_configured=settings.has_api_key,
            console_token_configured=bool(settings.console_token),
        ),
        stats=ConsoleStats(**stats),
        recent=[ConsoleRequestRecord(**item) for item in metrics.snapshot(limit=30)],
    )


@router.delete(
    "/api/v1/console/requests",
    dependencies=[Depends(require_console_access)],
    summary="清空内存中的请求记录",
)
async def clear_requests(metrics: RequestMetrics = Depends(get_metrics)) -> dict[str, bool]:
    metrics.clear()
    return {"cleared": True}
