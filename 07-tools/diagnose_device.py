"""设备离线诊断：串口 / 局域网 / 语音连接记录 / 控制台心跳。"""
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import serial.tools.list_ports

sys.stdout.reconfigure(encoding="utf-8")

print("======== 1) 串口 ========")
ports = [(p.device, p.description) for p in serial.tools.list_ports.comports()]
for d, desc in ports:
    print(f"  {d}: {desc}")
if not any(d.startswith("COM4") for d, _ in ports):
    print("  ⚠ COM4 不存在（设备未通过 USB 连接）")

print("\n======== 2) 局域网 ARP（找设备 MAC <设备MAC>）========")
try:
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True, encoding="gbk", errors="ignore").stdout
    hit = [ln.strip() for ln in out.splitlines() if "1c-29-04" in ln.lower() or "1c:29:04" in ln.lower()]
    print("  " + ("\n  ".join(hit) if hit else "未在 ARP 表中找到该 MAC（设备未上线）"))
except Exception as e:
    print("  arp 失败:", e)

print("\n======== 3) 语音服务是否收到过设备 WS 请求 ========")
log = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\tmp\server.log")
if log.exists():
    lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    hello = [ln for ln in lines[-4000:] if "helloHandle" in ln or "客户端音频格式" in ln]
    print(f"  最近 4000 行内 hello 记录: {len(hello)} 条")
    for ln in hello[-3:]:
        print("   ", ln[-100:])
    last = lines[-1] if lines else ""
    print("  日志最后一行:", last[-100:])
else:
    print("  日志不存在")

print("\n======== 4) 控制台设备心跳 ========")
try:
    import httpx
    c = httpx.Client(base_url="http://127.0.0.1:8080", timeout=15)
    c.post("/login", data={"password": "xiaohui2026"})
    st = c.get("/api/console/status").json()
    print("  在线连接数:", st.get("count"))
    devs = c.get("/api/devices").json().get("devices") or []
    for d in devs:
        ts = d.get("last_seen") or 0
        age = int(time.time() - ts) if ts else None
        print(f"  设备 {d.get('mac')} | IP {d.get('ip')} | 版本 {d.get('firmware')} | 最后在线 {age} 秒前")
except Exception as e:
    print("  失败:", type(e).__name__, e)

print("\n======== 5) 本机 IP / 端口 ========")
host = socket.gethostname()
ips = []
try:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*'}).IPAddress"],
                         capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
    ips = [x.strip() for x in out.splitlines() if x.strip()]
except Exception:
    pass
print("  本机 IPv4:", ips)
for port in (8000, 8080):
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", port))
        print(f"  端口 {port}: 可连接")
    except Exception:
        print(f"  端口 {port}: 不通")
    finally:
        s.close()
