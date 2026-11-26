import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://127.0.0.1:8080", timeout=25)
c.post("/login", data={"password": "xiaohui2026"})

aid = c.get("/api/agents").json()["agents"][0]["id"]
a = c.get("/api/agents/" + aid).json()
body = {k: a[k] for k in ("name", "persona", "model", "voice", "kb_enabled", "kb_topk", "memory_enabled")}
body["wake_word"] = "小慧小慧"
body["temperature"] = a.get("temperature", 0.7)
r = c.put("/api/agents/" + aid, json=body)
print("改唤醒词为「小慧小慧」:", r.status_code)

hb = c.post("/api/devices/heartbeat",
            json={"mac": "<设备MAC>", "firmware": "2.5.2"},
            headers={"X-Device-Token": "<REDACTED>"}).json()
print("心跳下发:", hb.get("config", {}).get("wake_words"))

# 改回
body["wake_word"] = "你好小慧"
c.put("/api/agents/" + aid, json=body)
hb2 = c.post("/api/devices/heartbeat",
             json={"mac": "<设备MAC>", "firmware": "2.5.2"},
             headers={"X-Device-Token": "<REDACTED>"}).json()
print("改回后:", hb2.get("config", {}).get("wake_words"))
