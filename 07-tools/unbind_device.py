import httpx
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=15)
c.post("/login", data={"password": "xiaohui2026"})

for d in c.get("/api/devices").json()["devices"]:
    c.post("/api/devices/" + d["id"] + "/unbind")
    print("已解绑:", d["mac"])

print("设备:", json.dumps(c.get("/api/devices").json()["devices"], ensure_ascii=False))
