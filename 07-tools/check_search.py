import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=30)
c.post("/login", data={"password": "xiaohui2026"})

queries = ["电池能用多久", "怎么唤醒", "舵机发热正常吗", "今天天气怎么样"]
for q in queries:
    r = c.post("/api/kb/search", json={"query": q, "top_k": 2}).json()
    hits = r.get("hits", [])
    if hits:
        top = hits[0]
        snippet = top["text"][:32].replace("\n", " ")
        print(f"{q:<10} -> {len(hits)} 条 | {top['score']:.3f} {snippet}")
    else:
        print(f"{q:<10} -> 无命中")
