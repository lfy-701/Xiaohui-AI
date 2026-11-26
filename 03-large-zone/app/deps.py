"""FastAPI 依赖。测试中通过 app.dependency_overrides 替换。"""

from __future__ import annotations

from fastapi import Request

from app.config import Settings
from app.metrics import RequestMetrics
from app.services.deepseek_client import DeepSeekClient


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_deepseek_client(request: Request) -> DeepSeekClient:
    return request.app.state.deepseek


def get_metrics(request: Request) -> RequestMetrics:
    return request.app.state.metrics
