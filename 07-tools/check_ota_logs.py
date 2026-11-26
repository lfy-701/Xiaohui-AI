import datetime
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=20)
c.post("/login", data={"password": "xiaohui2026"})

logs = c.get("/api/logs?limit=300").json()["logs"]
ota = [x for x in logs if "OTA" in x["text"]]
print("近 300 条日志里 OTA 相关:", len(ota))
for x in ota[:8]:
    ts = datetime.datetime.fromtimestamp(x["at"]).strftime("%m-%d %H:%M:%S")
    print("  {}  {}".format(ts, x["text"]))

print("\n所有日志最近 5 条：")
for x in logs[:5]:
    ts = datetime.datetime.fromtimestamp(x["at"]).strftime("%m-%d %H:%M:%S")
    print("  {}  [{}] {}".format(ts, x["role"], x["text"][:60]))

print("\n设备状态：")
devs = c.get("/api/devices").json()["devices"]
for d in devs:
    last = datetime.datetime.fromtimestamp(d["last_seen"]).strftime("%m-%d %H:%M:%S") if d["last_seen"] else "-"
    print("  {}  绑定={}  码={}  最后心跳={}".format(d["mac"], d["bound"], d["code"], last))
