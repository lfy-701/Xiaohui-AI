import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=120)
c.post("/login", data={"password": "xiaohui2026"})

aid = c.get("/api/agents").json()["agents"][0]["id"]
sid = "mcp-test-1"
c.post(f"/api/agents/{aid}/chat/reset", json={"session_id": sid})

for q in ["深圳现在天气怎么样", "帮我查一下北京明天的天气"]:
    r = c.post(f"/api/agents/{aid}/chat", json={"text": q, "session_id": sid})
    print("=" * 66)
    print("问:", q, "|", r.status_code)
    if r.status_code == 200:
        print("答:", r.json()["reply"][:400].replace("\n", " "))
    else:
        print("错误:", r.text[:200])

print("\n=== 调用记录 ===")
d = c.get("/api/mcp/calls?limit=5")
print(d.status_code, d.text[:500])
