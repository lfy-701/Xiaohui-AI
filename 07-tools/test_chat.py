import httpx

c = httpx.Client(base_url="http://127.0.0.1", timeout=30)
c.post("/login", data={"password": "xiaohui2026"})
aid = c.get("/api/agents").json()["agents"][0]["id"]
sid = "test-session-1"

for i, t in enumerate(["我叫小明", "我叫什么名字？"], 1):
    r = c.post(f"/api/agents/{aid}/chat", json={"text": t, "session_id": sid}).json()
    first = r["reply"].splitlines()[0][:60]
    print(f"第{i}轮 | turns={r['turns']} | {first}")

h = c.get(f"/api/agents/{aid}/chat/history", params={"session_id": sid}).json()
print("历史条数:", len(h["messages"]))
print("角色序列:", [m["role"] for m in h["messages"]])

c.post(f"/api/agents/{aid}/chat/reset", json={"session_id": sid})
left = c.get(f"/api/agents/{aid}/chat/history", params={"session_id": sid}).json()
print("清空后:", len(left["messages"]))
