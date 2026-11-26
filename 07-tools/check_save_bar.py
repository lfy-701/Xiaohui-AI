import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://xiaohui.me", timeout=25)
c.post("/login", data={"password": "xiaohui2026"})
h = c.get("/").text

print("=== 页面元素 ===")
for k in ["cfg-actions", "saveConfigNow()", "revertConfig()", "setSaveState",
          "已自动保存", "保存"]:
    print("  {:<20} {}".format(k, "OK" if k in h else "缺失"))

# 粗查 JS 括号是否平衡（只统计 script 段）
m = re.search(r"<script>(.*?)</script>", h, re.S)
if m:
    js = m.group(1)
    print("\n=== JS 括号平衡 ===")
    for a, b in [("{", "}"), ("(", ")"), ("[", "]")]:
        print("  {} {}  ->  {}".format(a, b, js.count(a) - js.count(b)))

# 保存功能实测：改音色后保存
print("\n=== 保存流程实测 ===")
aid = c.get("/api/agents").json()["agents"][0]["id"]
agent = c.get("/api/agents/" + aid).json()
old_voice = agent["voice"]
new_voice = "zh-CN-YunyangNeural" if old_voice != "zh-CN-YunyangNeural" else "zh-CN-XiaoxiaoNeural"
r = c.put("/api/agents/" + aid, json={
    "name": agent["name"], "persona": agent["persona"], "model": agent["model"],
    "voice": new_voice, "wake_word": agent["wake_word"],
    "kb_enabled": agent["kb_enabled"], "kb_topk": agent["kb_topk"],
    "memory_enabled": agent["memory_enabled"], "temperature": agent.get("temperature", 0.7),
})
print("  PUT:", r.status_code, "音色", old_voice, "→", r.json()["voice"])
print("  运行时:", c.get("/api/voice/settings").json().get("voice"))
