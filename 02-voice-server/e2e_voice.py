"""端到端测试：合成一段语音 → 按设备协议推给语音服务端 → 收回音频。

用法（在 voice-server 的 venv 里跑）：
    python e2e_voice.py
"""
import asyncio
import io
import json
import subprocess
import sys
import wave
from pathlib import Path

import edge_tts
import opuslib_next
import websockets

sys.stdout.reconfigure(encoding="utf-8")

WS_URL = "ws://127.0.0.1:8000/xiaozhi/v1/"
DEVICE_ID = "<设备MAC>"
CLIENT_ID = "e2e-test-0001"
QUESTION = "你好，请用一句话介绍一下你自己"
SAMPLE_RATE = 16000
FRAME_MS = 60
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 960


async def sz_make_pcm(text: str) -> bytes:
    """用 Edge TTS 合成语音，再转成 16k 单声道 s16le PCM。"""
    mp3 = Path("tmp/_e2e.mp3")
    mp3.parent.mkdir(exist_ok=True)
    wav = Path("tmp/_e2e.wav")

    async def synth():
        comm = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        with open(mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    f.write(chunk["data"])

    await synth()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
         "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", str(wav)],
        check=True,
    )
    return wav.read_bytes()


def encode_opus(pcm: bytes):
    enc = opuslib_next.Encoder(SAMPLE_RATE, 1, opuslib_next.APPLICATION_VOIP)
    enc.bitrate = 24000
    step = FRAME_SAMPLES * 2  # 16bit
    out = []
    for i in range(0, len(pcm) - step + 1, step):
        out.append(enc.encode(pcm[i:i + step], FRAME_SAMPLES))
    return out


async def main():
    pcm = await sz_make_pcm(QUESTION)
    frames = encode_opus(pcm)
    print(f"问题：{QUESTION}")
    print(f"PCM {len(pcm)} 字节 → Opus {len(frames)} 帧（每帧 {FRAME_MS}ms）")

    headers = {
        "Authorization": "Bearer test-token",
        "Protocol-Version": "1",
        "Device-Id": DEVICE_ID,
        "Client-Id": CLIENT_ID,
    }

    got_text = []
    got_audio = []

    async with websockets.connect(WS_URL, additional_headers=headers) as ws:
        print("已连接", WS_URL)

        # 1) hello
        await ws.send(json.dumps({
            "type": "hello",
            "device_id": DEVICE_ID,
            "device_name": "e2e",
            "device_mac": DEVICE_ID,
            "token": "",
            "features": {"mcp": False},
            "audio_params": {"format": "opus", "sample_rate": SAMPLE_RATE,
                             "channels": 1, "frame_duration": FRAME_MS},
        }))

        async def reader():
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=45)
                    if isinstance(msg, bytes):
                        got_audio.append(msg)
                        continue
                    data = json.loads(msg)
                    t = data.get("type")
                    if t == "hello":
                        print("  ← hello 握手成功")
                    elif t == "stt":
                        txt = data.get("text", "")
                        print(f"  ← ASR: {txt}")
                        got_text.append(("stt", txt))
                    elif t == "tts":
                        st = data.get("state")
                        if st == "sentence_start":
                            print(f"  ← TTS: {data.get('text','')[:60]}")
                    elif t == "llm":
                        print(f"  ← LLM emotion: {data.get('emotion')}")
                    elif t in ("listen",):
                        pass
                    else:
                        print(f"  ← {t}: {str(data)[:100]}")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print("  reader 结束:", type(e).__name__)

        rtask = asyncio.create_task(reader())
        await asyncio.sleep(1.0)

        # 2) 开始聆听 → 推音频 → 结束聆听
        await ws.send(json.dumps({"type": "listen", "state": "start", "mode": "auto"}))
        await asyncio.sleep(0.3)
        for f in frames:
            await ws.send(f)
            await asyncio.sleep(FRAME_MS / 1000)
        await asyncio.sleep(0.5)
        await ws.send(json.dumps({"type": "listen", "state": "stop"}))
        print("音频推送完毕，等待回复…")

        await asyncio.sleep(25)
        rtask.cancel()

    total = sum(len(x) for x in got_audio)
    print(f"\n收到 TTS 音频 {len(got_audio)} 帧 / {total} 字节")

    if got_audio:
        import wave
        dec = opuslib_next.Decoder(16000, 1)
        pcm = bytearray()
        for pkt in got_audio:
            try:
                pcm.extend(dec.decode(pkt, 960))
            except Exception:
                pass
        with wave.open("tmp/_reply.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(bytes(pcm))
        import numpy as np
        arr = np.frombuffer(bytes(pcm), dtype=np.int16)
        print(f"解码出 {len(pcm)} 字节 PCM / {len(arr)/16000:.2f} 秒 / "
              f"RMS {np.sqrt(np.mean(arr.astype(np.float64)**2)):.0f} / 峰值 {np.abs(arr).max()}")
        print("已保存 tmp/_reply.wav")
    if got_audio:
        # 音频已在上面解码为 tmp/_reply.wav
        pass

    for kind, txt in got_text:
        print(f"  {kind}: {txt}")


if __name__ == "__main__":
    asyncio.run(main())
