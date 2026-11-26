"""验证：记忆系统已接入（聊天后自动抽取事实）。"""
import httpx
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=40)
c.post("/login", data={"password": "xiaohui2026"})

aid = c.get("/api/agents").json()["agents"][0]["id"]

# 清掉这个会话的历史
sid = "mem-test"
c.post(f"/api/agents/{aid}/chat/reset", json={"session_id": sid})

before = c.get(f"/api/agents/{aid}/memory").json()
print("对话前记忆条数:", len(before.get("facts", [])))

# 说一句包含个人信息的话
r = c.post(f"/api/agents/{aid}/chat",
           json={"text": "我叫李明，我住在成都", "session_id": sid}).json()
print("对话回复:", r["reply"].splitlines()[0][:40])

after = c.get(f"/api/agents/{aid}/memory").json()
print("对话后记忆条数:", len(after.get("facts", [])))
for f in after.get("facts", []):
    print(f"   {f['slot']} = {f['value']} （{f['kind']}）")
