"""验证本地 opus 编解码是否正常：编码再解码，比对波形。"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import opuslib_next

sys.stdout.reconfigure(encoding="utf-8")

SR = 16000
FRAME = 960

wav = Path("tmp/_e2e.wav")           # ffmpeg 生成的 raw s16le
if not wav.exists():
    print("缺少 tmp/_e2e.wav，先跑 e2e_voice.py 的第一段")
    sys.exit(1)

pcm = wav.read_bytes()
samples = np.frombuffer(pcm, dtype=np.int16)
print(f"原始 PCM: {len(pcm)} 字节 / {len(samples)} 采样 / {len(samples)/SR:.2f} 秒")
print(f"原始 RMS: {np.sqrt(np.mean(samples.astype(np.float64)**2)):.1f}  "
      f"峰值: {np.abs(samples).max()}")

enc = opuslib_next.Encoder(SR, 1, opuslib_next.APPLICATION_VOIP)
enc.bitrate = 24000
dec = opuslib_next.Decoder(SR, 1)

frames = []
step = FRAME * 2
for i in range(0, len(pcm) - step + 1, step):
    frames.append(enc.encode(pcm[i:i + step], FRAME))
print(f"编码出 {len(frames)} 帧")

out = bytearray()
for f in frames:
    out.extend(dec.decode(f, FRAME))
dec_samples = np.frombuffer(bytes(out), dtype=np.int16)
print(f"解码后: {len(out)} 字节 / {len(dec_samples)} 采样")
print(f"解码 RMS: {np.sqrt(np.mean(dec_samples.astype(np.float64)**2)):.1f}  "
      f"峰值: {np.abs(dec_samples).max()}")

# 保存解码结果为 wav，便于人工听
with wave.open("tmp/_roundtrip.wav", "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(bytes(out))
print("已保存 tmp/_roundtrip.wav")
