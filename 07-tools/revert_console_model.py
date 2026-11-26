"""把控制台智能体模型改回快速小模型 xiaohui-r5，并测延迟。"""
import sqlite3
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")

db = r"D:\AI-Companion-shared\xiaohui-ai\console\data\console.db"
con = sqlite3.connect(db)
con.execute("UPDATE agents SET model='xiaohui-r5:latest'")
con.commit()
for row in con.execute("SELECT name, model FROM agents"):
    print("  智能体:", row)

print("\n=== 测速 ===")
h = httpx.Client(base_url="http://127.0.0.1:8080", timeout=90)
h.post("/login", data={"password": "xiaohui2026"})
ag = h.get("/api/agents").json()
ag = ag.get("agents") if isinstance(ag, dict) else ag
aid = ag[0]["id"]

for q in ("你好呀", "今天心情不错"):
    sid = f"rv{int(time.time()*1000)}"
    t0 = time.time()
    d = h.post(f"/api/agents/{aid}/chat", json={"text": q, "session_id": sid}, timeout=90).json()
    ms = int((time.time() - t0) * 1000)
    reply = (d.get("reply") or "").replace("\n", " ")[:42]
    print(f"  {q:10} {ms:5d}ms {reply}")
