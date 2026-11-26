import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://xiaohui.me", timeout=20)
c.post("/login", data={"password": "xiaohui2026"})
h = c.get("/").text

keys = ["cfg-tabs", "cfg-role", "cfg-model", "cfg-voice", "f-temp",
        "f-persona-custom", "switchCfgTab", "togglePersonaCustom", "onTempChange"]
for k in keys:
    print("  {:<22} {}".format(k, "OK" if k in h else "缺失"))

print()
models = c.get("/api/models").json().get("models", [])
print("  可用模型:", models)

# 切到模型 qwen2.5:3b 并检查同步
aid = c.get("/api/agents").json()["agents"][0]["id"]
agent = c.get("/api/agents/" + aid).json()
print("  当前 agent 模型:", agent.get("model"), "| 温度:", agent.get("temperature"))
r = c.put("/api/agents/" + aid, json={
    "name": agent["name"], "persona": agent["persona"],
    "model": "qwen2.5:3b", "voice": agent["voice"],
    "wake_word": agent["wake_word"],
    "kb_enabled": agent["kb_enabled"], "kb_topk": agent["kb_topk"],
    "memory_enabled": agent["memory_enabled"], "temperature": 0.6,
})
print("  更新后:", r.status_code, r.json().get("model"), r.json().get("temperature"))
print("  运行时设置:", c.get("/api/voice/settings").json())
