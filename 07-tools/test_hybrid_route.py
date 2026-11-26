"""独立验证混合路由：不导入语音服务（避免 opus 依赖），直接调专区并复现路由规则。"""
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DEEP_WORDS = (
    "为什么", "怎么理解", "解释", "分析", "原理", "推导", "证明",
    "作业", "数学题", "解题", "作文", "写好", "区别", "比较",
    "详细说说", "深入", "科普", "原理是什么", "怎么做",
)
MIN_LEN = 18


def route(text: str) -> str:
    hit = any(w in text for w in DEEP_WORDS)
    if hit or len(text) >= MIN_LEN:
        return "专区"
    return "本地"


cases = [
    "你好呀",
    "在吗",
    "今天天气怎么样",
    "为什么天空是蓝色的",
    "帮我分析一下这道数学题该怎么做",
    "陪我聊聊天吧我有点无聊想找人说说话",
]
print("=== 路由判定 ===")
for c in cases:
    print(f"  {route(c)}  | {c}")

print("\n=== 专区真实调用 ===")
try:
    r = httpx.post(
        "http://127.0.0.1:8013/api/v1/chat",
        json={"message": "为什么天空是蓝色的", "history": []},
        timeout=30,
    )
    print("  状态:", r.status_code)
    data = r.json()
    print("  回复:", (data.get("reply") or "")[:80])
    print("  用量:", data.get("usage"))
except Exception as e:
    print("  失败:", type(e).__name__, str(e)[:80])
