"""测试检索接口：命中片段、分数、段号。"""
import httpx
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=30)
c.post("/login", data={"password": "xiaohui2026"})

queries = ["电池能用多久", "怎么唤醒", "舵机发热正常吗", "今天天气怎么样"]

for q in queries:
    r = c.post("/api/kb/search", json={"query": q, "top_k": 3}).json()
    hits = r.get("hits", [])
    print(f"\n问：{q}  →  命中 {len(hits)} 段")
    for h in hits:
        print(f"   {h['score']:.3f}  {h['title']} 第{h.get('ord', 0) + 1}段  {h['text'][:38].replace(chr(10), ' ')}…")

h = c.get("/").text
print("\n前端含检索测试:", "testSearch" in h, "| 分数徽标:", "badge-score" in h)
