"""验证控制台网页对话：新会话 + 直接看专区返回。"""
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")

h = httpx.Client(base_url="http://127.0.0.1:8080", timeout=90)
h.post("/login", data={"password": "xiaohui2026"})
agents = h.get("/api/agents").json()
agents = agents.get("agents") if isinstance(agents, dict) else agents
aid = agents[0]["id"]

for q in ("你好呀", "今天东莞天气怎么样", "为什么天空是蓝色的"):
    sid = f"fresh{int(time.time()*1000)}"
    t0 = time.time()
    r = h.post(f"/api/agents/{aid}/chat", json={"text": q, "session_id": sid}, timeout=90)
    ms = int((time.time() - t0) * 1000)
    try:
        d = r.json()
        reply = (d.get("reply") or "").replace("\n", " ")[:70]
        model = d.get("model")
    except Exception:
        reply, model = r.text[:70], "?"
    print(f"  {q:16} {ms:6d}ms [{model}] {reply}")

print("\n=== 专区独立验证 ===")
for q in ("你好呀", "今天东莞天气怎么样"):
    d = httpx.post("http://127.0.0.1:8013/api/v1/chat",
                   json={"message": q, "history": []}, timeout=40).json()
    print(f"  {q:16} [{d.get('model')}] {(d.get('reply') or '')[:50]}")
