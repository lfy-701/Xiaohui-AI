import datetime
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://127.0.0.1:8080", timeout=20)
c.post("/login", data={"password": "xiaohui2026"})

print("=== 设备列表 ===")
for d in c.get("/api/devices").json()["devices"]:
    seen = "-"
    if d.get("last_seen"):
        seen = datetime.datetime.fromtimestamp(d["last_seen"]).strftime("%m-%d %H:%M:%S")
    print(
        "  {name}  mac={mac}  fw={fw}  bound={bound}  最后心跳={seen}".format(
            name=d["name"],
            mac=d["mac"],
            fw=d.get("firmware", "-"),
            bound=d["bound"],
            seen=seen,
        )
    )

logs = c.get("/api/logs?limit=80").json()["logs"]
now = datetime.datetime.now()
recent = [
    x
    for x in logs
    if (now - datetime.datetime.fromtimestamp(x["at"])).total_seconds() < 7200
]
print("\n=== 最近 2 小时日志 " + str(len(recent)) + " 条 ===")
for x in recent[:10]:
    t = datetime.datetime.fromtimestamp(x["at"]).strftime("%H:%M:%S")
    print("  {t}  [{k}] {text}".format(t=t, k=x["kind"], text=x["text"][:58]))

print("\n=== 语音服务 WebSocket 端口 ===")
import socket

for port in (8000, 8080, 80):
    s = socket.socket()
    s.settimeout(1)
    ok = s.connect_ex(("127.0.0.1", port)) == 0
    s.close()
    print("  {p} -> {s}".format(p=port, s="监听中" if ok else "未监听"))
