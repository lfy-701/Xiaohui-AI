"""验证分段预览接口。"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://127.0.0.1", timeout=30)
c.post("/login", data={"password": "xiaohui2026"})

docs = c.get("/api/kb/docs").json().get("docs", [])
print("文档数:", len(docs))
if not docs:
    print("没有文档，先导入一篇")
    txt = "小慧 使用说明。\n\n小慧是一只 AI 桌面机器狗，主控 ESP32-S3。\n\n它配有 OLED 屏幕和六路舵机。\n\n电池为 3.7V 锂电池。"
    r = c.post("/api/kb/ingest_text", json={"title": "分段测试", "text": txt}).json()
    print("已导入:", r)
    docs = c.get("/api/kb/docs").json()["docs"]

doc = docs[0]
print("预览文档:", doc["title"], "| 切片数:", doc["chunks"])

r = c.get(f"/api/kb/docs/{doc['id']}/chunks").json()
print("count:", r["count"])
for ch in r["chunks"]:
    preview = ch["text"].replace("\n", " ")[:50]
    print(f"  #{ch['ord'] + 1} ({ch['chars']} 字): {preview}")

h = c.get("/").text
print("\n前端含 openChunks:", "openChunks" in h)
print("前端含 chunkPanel:", "chunkPanel" in h)
