"""按成员 A 的验收清单逐项测试控制台 ↔ 模型服务。"""
import httpx
import json

BASE = "http://127.0.0.1"
c = httpx.Client(base_url=BASE, timeout=60)
c.post("/login", data={"password": "xiaohui2026"})

print("=== 1) 模型列表 ===")
st = c.get("/api/models").json()
print(json.dumps(st, ensure_ascii=False, indent=1))

aid = c.get("/api/agents").json()["agents"][0]["id"]

print("\n=== 2) 设置智能体模型为 qwen2.5:3b ===")
r = c.put(f"/api/agents/{aid}", json={"model": "qwen2.5:3b"}).json()
print("当前模型:", r["model"])

print("\n=== 3) 普通对话 ===")
sid = "acc-1"
c.post(f"/api/agents/{aid}/chat/reset", json={"session_id": sid})
d = c.post(f"/api/agents/{aid}/chat", json={"text": "你好", "session_id": sid}).json()
print("回复:", d["reply"].replace("\n", " | "))
print("turns:", d["turns"], "kb_hits:", d["kb_hits"])

print("\n=== 4) 多轮上下文 ===")
d2 = c.post(f"/api/agents/{aid}/chat", json={"text": "你叫几轮", "session_id": sid}).json()
print("回复:", d2["reply"].replace("\n", " | "))
print("turns:", d2["turns"])

print("\n=== 5) 流式 SSE ===")
chunks = []
with c.stream("POST", f"/api/agents/{aid}/chat/stream",
              json={"text": "流式测试", "session_id": sid}) as r:
    print("Content-Type:", r.headers.get("content-type"))
    for line in r.iter_lines():
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            print("收到 [DONE]")
            break
        obj = json.loads(data)
        if "delta" in obj:
            chunks.append(obj["delta"])
        elif "error" in obj:
            print("错误事件:", obj["error"])
print("分块数:", len(chunks), "| 拼接:", "".join(chunks)[:70])

print("\n=== 6) 错误处理：不存在的模型 ===")
c.put(f"/api/agents/{aid}", json={"model": "不存在模型"})
bad = c.post(f"/api/agents/{aid}/chat", json={"text": "hi", "session_id": "err-1"}).json()
print("返回:", bad["reply"][:120].replace("\n", " "))
c.put(f"/api/agents/{aid}", json={"model": "qwen2.5:3b"})
print("\n已恢复模型为 qwen2.5:3b")
