"""分离测：需要工具 vs 不需要工具，以及 TTS 冷/热首包。"""
import asyncio
import json
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8")

LLM_URL = "http://<本地模型服务器IP>:8000/v1/chat/completions"
SYS = "你是小慧，说话温柔自然，回答简短，两三句说完。"


def bench(prompt, note):
    t0 = time.time()
    first = None
    text = ""
    with httpx.stream("POST", LLM_URL, timeout=90, json={
        "model": "qwen2.5:3b",
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "stream": True,
    }) as r:
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            d = line[6:]
            if d.strip() == "[DONE]":
                break
            try:
                obj = json.loads(d)
                delta = obj["choices"][0]["delta"].get("content") or ""
                if delta:
                    if first is None:
                        first = time.time() - t0
                    text += delta
            except Exception:
                continue
    total = time.time() - t0
    print(f"  {note:<18} 首字 {(first or 0)*1000:>6.0f} ms | 完整 {total*1000:>6.0f} ms")
    print(f"    → {text[:50]}")


async def tts_once(label):
    import edge_tts
    t0 = time.time()
    comm = edge_tts.Communicate("好呀，我在呢。", voice="zh-CN-XiaoxiaoNeural", rate="+25%")
    first = None
    async for ch in comm.stream():
        if ch.get("type") == "audio" and first is None:
            first = time.time() - t0
    print(f"  {label:<18} 首包 {(first or 0)*1000:>6.0f} ms")


print("=== LLM：是否触发工具 ===")
bench("你好呀", "纯闲聊（无工具）")
bench("今天天气怎么样？", "需要天气工具")
bench("讲个短笑话", "纯生成")

print("\n=== TTS：冷启动 vs 热连接 ===")
asyncio.run(tts_once("第一次（冷）"))
asyncio.run(tts_once("第二次（热）"))
asyncio.run(tts_once("第三次（热）"))
