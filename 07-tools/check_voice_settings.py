"""验证语音设置是否真的生效：对比不同语速/音调下的合成音频时长。"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts

sys.stdout.reconfigure(encoding="utf-8")

SRV = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
FILE = SRV / "data" / "voice_settings.json"
TEXT = "你好呀，我是小慧，今天的天气很适合出去走走，要不要一起散散步？"


async def synth(rate: str, pitch: str) -> int:
    comm = edge_tts.Communicate(TEXT, voice="zh-CN-XiaoxiaoNeural", rate=rate, pitch=pitch)
    n = 0
    async for ch in comm.stream():
        if ch.get("type") == "audio":
            n += len(ch["data"])
    return n


def dur(bytes_, bitrate_kbps=48):
    # mp3 体积近似换算时长（Edge TTS 约 48kbps）
    return bytes_ * 8 / (bitrate_kbps * 1000)


def main():
    orig = FILE.read_text(encoding="utf-8")

    print("当前控制台保存的设置：")
    print(" ", json.dumps(json.loads(orig), ensure_ascii=False))

    for label, rate, pitch in [
        ("标准语速 +25%（当前设置）", "+25%", "+0Hz"),
        ("标准语速", "+0%", "+0Hz"),
        ("慢速 -10%", "-10%", "+0Hz"),
    ]:
        n = asyncio.run(synth(rate, pitch))
        print(f"  {label:<26} 音频 {n:>6} 字节  约 {dur(n):.2f} 秒")

    # 用语音服务里的 provider 真正走一遍（读文件 → 合成）
    from core.providers.tts.edge import TTSProvider

    provider = TTSProvider({"voice": "zh-CN-XiaoxiaoNeural", "format": "mp3"}, True)
    out = SRV / "tmp" / "_vs_test.mp3"
    asyncio.run(provider.text_to_speak("我是小慧，语速应该比默认快一些。", str(out)))
    size = out.stat().st_size
    print(f"\n  走语音服务 provider 合成：{size} 字节  约 {dur(size):.2f} 秒")
    print("  provider 读取的 rate =", json.loads(orig).get("rate"))
    out.unlink(missing_ok=True)


main()
