"""假设备客户端：用合成语音走一遍真实语音链路，复现/验证 ASR。

用法（语音服务 venv，且把 .venv\\Scripts 加进 PATH 以便加载 opus.dll）：
    .venv\\Scripts\\python.exe tools\\fake_device.py "今天东莞天气怎么样"

流程：edge-tts 合成 → 16k 单声道 PCM → opus 60ms 帧 → websocket 按设备协议发送
（hello → listen start → 音频帧 → listen stop），并把服务端返回的文本打印出来。
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server"
URL = "ws://127.0.0.1:8000/xiaozhi/v1/"
DEVICE_ID = "<设备MAC>"          # 复用真实设备 ID，避免走激活/绑定分支
CLIENT_ID = str(uuid.uuid4())

RATE = 16000
FRAME = 960          # 60ms @16k


def synth(text: str) -> bytes:
    """合成 16k/mono/s16le PCM。"""
    import edge_tts
    import imageio_ffmpeg

    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, "a.mp3")
    wav = os.path.join(tmp, "a.pcm")

    async def _tts():
        await edge_tts.Communicate(text, voice="zh-CN-XiaoxiaoNeural").save(mp3)

    asyncio.run(_tts())
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", mp3,
         "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(RATE), "-ac", "1", wav],
        check=True, timeout=90,
    )
    with open(wav, "rb") as f:
        return f.read()


def encode_frames(pcm: bytes):
    import opuslib_next as opus

    enc = opus.Encoder(RATE, 1, opus.APPLICATION_AUDIO)
    out = []
    for i in range(0, len(pcm), FRAME * 2):
        chunk = pcm[i:i + FRAME * 2]
        if len(chunk) < FRAME * 2:
            chunk += b"\x00" * (FRAME * 2 - len(chunk))
        out.append(enc.encode(chunk, FRAME))
    return out


async def run(text: str, pcm: bytes, wake: bool = False):
    import websockets

    frames = encode_frames(pcm)
    print(f"[fake] 合成 {len(pcm)/2/ RATE:.1f}s，{len(frames)} 帧", flush=True)

    headers = {"device-id": DEVICE_ID, "client-id": CLIENT_ID}
    async with websockets.connect(URL, additional_headers=headers) as ws:
        hello = {
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "features": {"mcp": True},
            "audio_params": {"format": "opus", "sample_rate": RATE,
                             "channels": 1, "frame_duration": 60},
        }
        await ws.send(json.dumps(hello))
        await asyncio.sleep(0.6)

        async def drain(seconds, label):
            """读出服务端消息，返回是否见到 tts stop。"""
            end = asyncio.get_event_loop().time() + seconds
            saw_stop = False
            while asyncio.get_event_loop().time() < end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if isinstance(msg, (bytes, bytearray)):
                    continue
                try:
                    obj = json.loads(msg)
                except Exception:
                    continue
                t = obj.get("type")
                if t == "stt":
                    print(f"[{label}][STT]", obj.get("text"), flush=True)
                elif t == "tts":
                    st = obj.get("state")
                    if st in ("start", "stop"):
                        print(f"[{label}][TTS]", st, flush=True)
                    if st == "stop":
                        saw_stop = True
                    if st == "sentence_start":
                        print(f"[{label}][TTS句]", obj.get("text"), flush=True)
                elif t in ("llm",):
                    print(f"[{label}][llm]", str(obj.get("emotion") or ""), flush=True)
            return saw_stop

        if wake:
            # 模拟设备端唤醒：上报 detect 文本 → 服务端固定短句应答
            await ws.send(json.dumps({"type": "listen", "state": "detect", "text": "你好小慧"}))
            print("[fake] 已上报唤醒词，等问候播完", flush=True)
            await drain(6, "wake")

        await ws.send(json.dumps({"type": "listen", "state": "start", "mode": "auto"}))
        await asyncio.sleep(0.2)
        for fr in frames:
            await ws.send(fr)
            await asyncio.sleep(0.06)
        await ws.send(json.dumps({"type": "listen", "state": "stop"}))
        await drain(90, "talk")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wake = "--wake" in sys.argv
    text = args[0] if args else "今天东莞天气怎么样"
    pcm_data = synth(text)          # 先同步合成，避免在事件循环里再开一个
    asyncio.run(run(text, pcm_data, wake))
