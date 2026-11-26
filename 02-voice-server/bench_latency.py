"""实测语音链路三段耗时：ASR / LLM 首字 / TTS 首包。"""
import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

LLM_URL = "http://<本地模型服务器IP>:8000/v1/chat/completions"
SYS = "你是小慧，主人身边最亲近的伙伴。说话温柔自然，回答简短，两三句说完。"
USER = "今天天气怎么样？"


def bench_llm():
    """首字延迟 + 完整耗时（流式）。"""
    t0 = time.time()
    first = None
    text = ""
    with httpx.stream("POST", LLM_URL, timeout=60, json={
        "model": "qwen2.5:3b",
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": USER}],
        "stream": True,
    }) as r:
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                import json
                d = json.loads(data)
                delta = d["choices"][0]["delta"].get("content") or ""
                if delta:
                    if first is None:
                        first = time.time() - t0
                    text += delta
            except Exception:
                continue
    total = time.time() - t0
    return first, total, text


async def bench_tts():
    import edge_tts
    t0 = time.time()
    comm = edge_tts.Communicate("今天天气不错，适合出去走走。", voice="zh-CN-XiaoxiaoNeural", rate="+25%")
    first = None
    n = 0
    async for ch in comm.stream():
        if ch.get("type") == "audio":
            if first is None:
                first = time.time() - t0
            n += len(ch["data"])
    return first, time.time() - t0, n


def bench_asr():
    """用语音服务里的 SenseVoiceSmall 跑一段现成音频。"""
    from funasr import AutoModel
    import soundfile as sf  # noqa: F401

    t0 = time.time()
    model = AutoModel(model="models/SenseVoiceSmall", device="cpu", disable_update=True)
    model_time = time.time() - t0

    wav = Path("tmp/_asr_probe.wav")
    if not wav.exists():
        import wave
        # 没有样本就跳过实际识别
        print("  （无 ASR 样本，跳过识别计时）")
        return model_time, None
    t1 = time.time()
    res = model.generate(input=str(wav), language="zh", use_itn=True)
    return model_time, time.time() - t1


print("=== LLM 首字延迟 ===")
f, t, txt = bench_llm()
print(f"  首字 {f*1000:.0f} ms | 完整 {t*1000:.0f} ms")
print(f"  回复: {txt[:60]}")

print("\n=== TTS 首包延迟 ===")
f, t, n = asyncio.run(bench_tts())
print(f"  首包 {f*1000:.0f} ms | 完整 {t*1000:.0f} ms | {n} 字节")

print("\n=== ASR 模型加载 ===")
mt, rt = bench_asr()
print(f"  加载 {mt*1000:.0f} ms" + (f" | 识别 {rt*1000:.0f} ms" if rt else ""))
