"""按 .env 中的 APP_HOST / APP_PORT 启动服务。

供“大模型专区”独立部署使用：控制台主机上单独一个进程、单独端口，
不读取、不修改现有小慧控制台的 console.db。
"""

from __future__ import annotations

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
