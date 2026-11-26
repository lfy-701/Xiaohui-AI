"""日志配置：统一格式，屏蔽 httpx/openai 的高频且可能含敏感 header 的日志。"""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    # 避免每个请求刷屏；也避免调试日志把 Authorization 带出来
    for noisy in ("httpx", "httpcore", "openai", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
