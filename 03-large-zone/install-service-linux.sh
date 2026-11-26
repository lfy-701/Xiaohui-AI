#!/usr/bin/env bash
# 小慧大模型专区 · 安装 systemd 服务（需要 sudo）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
UNIT="/etc/systemd/system/xiaohui-large.service"
RUN_USER="${SUDO_USER:-$USER}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 执行：sudo bash install-service-linux.sh" >&2
  exit 1
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "未找到 .venv，请先运行 bash install-linux.sh" >&2
  exit 1
fi

cat > "$UNIT" <<EOF
[Unit]
Description=Xiaohui Large Model Zone (port 8013)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python $ROOT/run_zone.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now xiaohui-large.service
systemctl --no-pager --full status xiaohui-large.service | head -n 20

echo ""
echo "已安装并启动。访问：http://127.0.0.1:8013/"
echo "查看日志：journalctl -u xiaohui-large -f"
echo "停止：systemctl stop xiaohui-large"
