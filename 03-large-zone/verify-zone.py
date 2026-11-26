"""大模型专区自检：健康检查 + 概览接口 + 可选对话。

用法（在专区目录）：
    .venv\Scripts\python.exe verify-zone.py
    .venv\Scripts\python.exe verify-zone.py --chat
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="小慧大模型专区自检")
    parser.add_argument("--base", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--chat", action="store_true", help="额外发一句真实对话（会消耗额度）")
    parser.add_argument("--message", default="你好，小慧，用一句话跟我打个招呼")
    args = parser.parse_args()

    port = os.getenv("APP_PORT", "8013")
    base = (args.base or f"http://127.0.0.1:{port}").rstrip("/")
    token = ""

    print(f"专区地址：{base}")

    health = requests.get(f"{base}/health", timeout=10)
    print(f"GET /health -> {health.status_code}")
    if health.status_code != 200:
        print(health.text[:300])
        return 1
    body = health.json()
    print(f"  status={body['status']} model={body['deepseek']['model']} "
          f"configured={body['deepseek']['configured']}")
    if not body["deepseek"]["configured"]:
        print("  ! 未配置 DEEPSEEK_API_KEY，请编辑 .env 后重启")
        return 1

    headers = {"X-Console-Token": token} if token else {}
    overview = requests.get(f"{base}/api/v1/console/overview", headers=headers, timeout=10)
    print(f"GET /api/v1/console/overview -> {overview.status_code}")
    if overview.status_code == 401:
        print("  ! 控制台令牌缺失或不正确，检查 .env 的 CONSOLE_TOKEN")
        return 1
    if overview.status_code != 200:
        print(overview.text[:300])
        return 1
    config = overview.json()["config"]
    print(f"  模型={config['model']} 深度思考默认={config['thinking_enabled']} "
          f"端口={port}")

    if args.chat:
        response = requests.post(
            f"{base}/api/v1/chat",
            json={"message": args.message, "device_id": "zone-check"},
            timeout=90,
        )
        print(f"POST /api/v1/chat -> {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  reply: {data['reply']}")
            print(f"  latency={data['latency_ms']} ms tokens={data['usage']['total_tokens']}")
        else:
            print(response.text[:300])
            return 1

    print("\n结果：通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
