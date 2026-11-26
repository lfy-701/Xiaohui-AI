#!/usr/bin/env bash
# 小慧大模型专区 · Linux 安装
# 用法：bash install-linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

INDEX_URL="${INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PY="${PYTHON:-python3.11}"

echo "=============================================="
echo " 小慧大模型专区 · 安装（独立进程 / 8013）"
echo "=============================================="

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "未找到 $PY，请先安装 Python 3.11（如 sudo apt install python3.11 python3.11-venv）" >&2
  exit 1
fi

echo "[1/4] Python: $($PY --version)"
if [ ! -x ".venv/bin/python" ]; then
  echo "[2/4] 创建独立虚拟环境 .venv ..."
  "$PY" -m venv .venv
else
  echo "[2/4] 复用已有 .venv"
fi

echo "[3/4] 安装依赖（镜像：$INDEX_URL）..."
.venv/bin/python -m pip install --disable-pip-version-check --upgrade pip --index-url "$INDEX_URL"
.venv/bin/pip install --disable-pip-version-check -r requirements.txt --index-url "$INDEX_URL"

echo "[4/4] 准备 .env ..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  已从 .env.example 创建 .env"
fi

if grep -q '^CONSOLE_TOKEN=[[:space:]]*$' .env; then
  TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(16))')"
  sed -i "s/^CONSOLE_TOKEN=.*/CONSOLE_TOKEN=${TOKEN}/" .env
  echo ""
  echo "  本次生成的控制台令牌：${TOKEN}"
fi

echo ""
echo "安装完成。下一步："
echo "  1) 编辑 .env，填入 DEEPSEEK_API_KEY"
echo "  2) 前台启动：.venv/bin/python run_zone.py"
echo "  3) 后台常驻：bash install-service-linux.sh（需要 sudo）"
echo "  4) 访问：http://127.0.0.1:8013/"
