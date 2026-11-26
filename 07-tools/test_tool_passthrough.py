"""测试成员 A 的模型服务是否会把设备工具透传给大模型。"""
import json
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://<本地模型服务器IP>:8000"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "self.dog_action",
            "description": "控制机器狗做动作。action 可选：stand(站立)、sit(坐下)、walk(前进)、wag(摇尾巴)、shake(摇头)、stop(停下)。",
            "parameters": {
                "type": "object",
                "properties": {"action": {"type": "string"}},
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "self.set_led",
            "description": "设置灯珠颜色。r/g/b 取值 0-255。",
            "parameters": {
                "type": "object",
                "properties": {
                    "r": {"type": "integer"},
                    "g": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["r", "g", "b"],
            },
        },
    },
]

print("=== 1) 服务可达性 ===")
try:
    r = httpx.get(BASE + "/v1/models", timeout=8)
    print("  /v1/models:", r.status_code)
    try:
        data = r.json()
        names = [m.get("id") for m in data.get("data", [])][:6]
        print("  可用模型:", names)
    except Exception:
        print("  返回非 JSON")
except Exception as e:
    print("  不可达:", type(e).__name__, str(e)[:80])

for prompt in ("站起来", "把灯变成红色"):
    print("\n=== 2) 工具调用测试: " + prompt + " ===")
    body = {
        "model": "qwen2.5:3b",
        "messages": [{"role": "user", "content": prompt}],
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.3,
        "max_tokens": 200,
    }
    try:
        r = httpx.post(BASE + "/v1/chat/completions", json=body, timeout=45)
        print("  HTTP:", r.status_code)
        d = r.json()
        ch = (d.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        print("  finish_reason:", ch.get("finish_reason"))
        print("  content:", (msg.get("content") or "")[:60])
        tc = msg.get("tool_calls")
        if tc:
            print("  ✅ tool_calls:", json.dumps(tc, ensure_ascii=False)[:200])
        else:
            print("  ❌ 没有 tool_calls")
        meta = d.get("metadata") or {}
        if meta:
            print("  metadata:", json.dumps(meta, ensure_ascii=False)[:200])
    except Exception as e:
        print("  请求失败:", type(e).__name__, str(e)[:80])
