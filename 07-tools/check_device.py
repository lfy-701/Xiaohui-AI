import datetime
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=20)
c.post("/login", data={"password": "xiaohui2026"})
d = c.get("/api/devices").json()["devices"][0]
ts = datetime.datetime.fromtimestamp(d["last_seen"]).strftime("%m-%d %H:%M:%S")
print("  {}  ip={}  绑定={}  最后心跳={}".format(d["name"], d["ip"], d["bound"], ts))

s = c.get("/api/stats").json()
print("  统计:", s.get("devices"))
