"""完整走一遍：未绑定 → 拿激活码 → 绑定 → 再请求 OTA 拿到 websocket。"""
import httpx
import json

BASE = "http://127.0.0.1"
MAC = "<设备MAC>"
body = {
    "version": 2,
    "mac_address": MAC,
    "uuid": "test-uuid",
    "application": {"name": "xiaozhi", "version": "2.5.2"},
}

c = httpx.Client(base_url=BASE, timeout=20)
c.post("/login", data={"password": "xiaohui2026"})

devs = c.get("/api/devices").json()["devices"]
dev = [d for d in devs if d["mac"] == MAC][0]

# 先解绑，模拟全新设备
c.post(f"/api/devices/{dev['id']}/unbind")
print("=== 1) 解绑后请求 OTA ===")
r1 = c.post("/ota/", json=body, headers={"Device-Id": MAC}).json()
print(json.dumps(r1, ensure_ascii=False, indent=1))

code = r1.get("activation", {}).get("code", "")
aid = c.get("/api/agents").json()["agents"][0]["id"]
c.post("/api/devices/bind", json={"code": code, "agent_id": aid})
print(f"\n已用激活码 {code} 绑定")

print("\n=== 2) 绑定后再请求 OTA ===")
r2 = c.post("/ota/", json=body, headers={"Device-Id": MAC}).json()
print(json.dumps(r2, ensure_ascii=False, indent=1))
