"""验证 P0：健康检查 + 知识库检索链路。"""
import json
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

print("=== 1) 健康检查 ===")
c = httpx.Client(base_url="http://127.0.0.1:8080", timeout=20)
c.post("/login", data={"password": "xiaohui2026"})
r = c.get("/api/health")
print("  状态码:", r.status_code)
d = r.json()
print("  总体:", "全部正常" if d.get("ok") else "有异常")
for k, v in (d.get("services") or {}).items():
    print(f"    {k}: {v}")

print("\n=== 2) 音乐健康 ===")
print("  /api/music/health:", c.get("/api/music/health").status_code)

print("\n=== 3) 知识库检索（语音直通用的同一接口）===")
try:
    kb = httpx.Client(timeout=20)
    for q in ("数学", "幼儿认知", "语言启蒙"):
        hits = kb.post("http://127.0.0.1:8077/kb/search",
                       json={"query": q, "top_k": 3}).json().get("hits") or []
        head = (hits[0].get("text") or hits[0].get("content") or "")[:50].replace("\n", " ") if hits else "-"
        print(f"  {q}: 命中 {len(hits)} 条 | {head}")
except Exception as e:
    print("  失败:", type(e).__name__, e)
