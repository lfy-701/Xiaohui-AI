"""FastAPI 应用入口。

启动方式：
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import chat as chat_api
from app.api import console as console_api
from app.api import health as health_api
from app.config import Settings, get_settings
from app.errors import AppError
from app.logging_conf import setup_logging
from app.metrics import RequestMetrics
from app.middleware import RequestContextMiddleware
from app.services.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    metrics = RequestMetrics(maxlen=200)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.settings = settings
        application.state.metrics = metrics
        application.state.started_at = time.monotonic()
        application.state.deepseek = DeepSeekClient(settings)

        logger.info(
            "服务启动 %s v%s | model=%s thinking=%s timeout=%ss/%ss retries=%d",
            settings.app_name,
            settings.version,
            settings.deepseek_model,
            "on" if settings.thinking_enabled else "off",
            settings.request_timeout_s,
            settings.total_timeout_s,
            settings.max_retries,
        )
        if not settings.has_api_key:
            logger.warning(
                "未配置 DEEPSEEK_API_KEY：/api/v1/chat 将返回 503。"
                "请复制 server/.env.example 为 server/.env 并填写密钥。"
            )

        try:
            yield
        finally:
            await application.state.deepseek.aclose()
            logger.info("服务已停止")

    application = FastAPI(
        title="ESP32 AI 小狗服务端",
        version=settings.version,
        description=(
            "AI 语音陪伴机器狗服务端。当前实现阶段 1（Windows 环境 + FastAPI 骨架）"
            "与阶段 2（DeepSeek 文字对话）。ASR/TTS 将在阶段 3 接入。"
        ),
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.metrics = metrics

    application.add_middleware(RequestContextMiddleware, metrics=metrics)

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        if exc.status_code >= 500:
            logger.error("业务错误 code=%s status=%s msg=%s rid=%s", exc.code, exc.status_code, exc.message, request_id)
        else:
            logger.warning("业务错误 code=%s status=%s msg=%s rid=%s", exc.code, exc.status_code, exc.message, request_id)

        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else None
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_payload(request_id),
            headers=headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for error in exc.errors()[:5]:
            location = ".".join(str(part) for part in error.get("loc", ()))
            details.append({"field": location, "message": error.get("msg", "")})

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "请求参数不合法",
                    "request_id": _request_id(request),
                    "details": details,
                }
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                    "request_id": _request_id(request),
                }
            },
            headers=getattr(exc, "headers", None),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常 rid=%s", _request_id(request))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "服务端内部错误，请查看日志",
                    "request_id": _request_id(request),
                }
            },
        )

    application.include_router(health_api.router)
    application.include_router(chat_api.router)
    application.include_router(console_api.router)

    # 启动预热：常用城市天气缓存（后台线程，不阻塞启动）
    try:
        from app.services.fast_answers import warmup_cities
        from app.services.tools import get_news

        warmup_cities()
        # 新闻也预热一次：首次问就不必等 RSS 抓取
        import threading as _th
        _th.Thread(target=lambda: get_news(3), name="news-warmup", daemon=True).start()
    except Exception:
        pass

    @application.get("/", include_in_schema=False)
    async def index(request: Request):
        # 浏览器直接访问根路径时进控制台；脚本仍拿到 JSON
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/console", status_code=307)
        return {
            "service": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "console": "/console",
            "health": "/health",
            "chat": "POST /api/v1/chat",
        }

    return application


app = create_app()
