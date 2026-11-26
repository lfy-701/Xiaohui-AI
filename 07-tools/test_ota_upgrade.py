"""验证：上传新固件后，设备请求 OTA 会收到升级通知。"""
import httpx
import json

BASE = "http://127.0.0.1"
MAC = "<设备MAC>"
body = {"mac_address": MAC, "application": {"version": "2.5.2"}}

c = httpx.Client(base_url=BASE, timeout=20)
r = c.post("/ota/", json=body, headers={"Device-Id": MAC}).json()
print("设备当前 2.5.2，OTA 返回：")
print(json.dumps(r, ensure_ascii=False, indent=1))

print("\n--- 设备已经是最新版本的情况 ---")
body2 = {"mac_address": MAC, "application": {"version": "2.6.0"}}
r2 = c.post("/ota/", json=body2, headers={"Device-Id": MAC}).json()
print("firmware 字段:", r2.get("firmware", "（无，已是最新）"))
