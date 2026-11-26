"""进程内请求指标：环形缓冲，不落库、不引入 Redis。

只记录方法、路径、状态码、耗时、请求 ID，**不记录请求/回复正文**，
避免把用户对话内容留在内存快照里。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

# 自身刷新/页面加载会产生大量噪声，不记录
IGNORED_PREFIXES = (
    "/api/v1/console",
    "/console",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)
IGNORED_EXACT = {"/"}


@dataclass(frozen=True, slots=True)
class RequestRecord:
    ts: str
    method: str
    path: str
    status: int
    latency_ms: int
    request_id: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RequestMetrics:
    def __init__(self, maxlen: int = 200) -> None:
        self._records: deque[RequestRecord] = deque(maxlen=maxlen)
        self._total = 0
        self._errors = 0

    def record(
        self,
        *,
        method: str,
        path: str,
        status: int,
        latency_ms: int,
        request_id: str,
    ) -> None:
        if path in IGNORED_EXACT or path.startswith(IGNORED_PREFIXES):
            return
        self._records.append(
            RequestRecord(
                ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                method=method,
                path=path,
                status=status,
                latency_ms=latency_ms,
                request_id=request_id,
            )
        )
        self._total += 1
        if status >= 400:
            self._errors += 1

    def snapshot(self, limit: int = 30) -> list[dict[str, Any]]:
        records = list(self._records)
        return [item.as_dict() for item in reversed(records[-limit:])]

    def stats(self) -> dict[str, Any]:
        recent = list(self._records)
        latencies = [item.latency_ms for item in recent]
        return {
            "total_requests": self._total,
            "error_requests": self._errors,
            "avg_latency_ms": int(mean(latencies)) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "sample_size": len(latencies),
        }

    def clear(self) -> None:
        self._records.clear()
        self._total = 0
        self._errors = 0
