"""绕过服务端，直接用 funasr 加载 SenseVoiceSmall 识别我们的测试音频。"""
import sys
import wave

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

model_dir = "models/SenseVoiceSmall"
wav_path = "tmp/_roundtrip.wav"

with wave.open(wav_path, "rb") as w:
    sr = w.getframerate()
    data = w.readframes(w.getnframes())
audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
print(f"音频: {len(audio)} 采样 / {len(audio)/sr:.2f} 秒 / 采样率 {sr}")

from funasr import AutoModel

model = AutoModel(
    model=model_dir,
    trust_remote_code=True,
    remote_code="./model.py",

    device="cpu",
    disable_update=True,
)

res = model.generate(
    input=audio,
    cache={},
    language="zh",
    use_itn=True,
    batch_size_s=60,
    merge_vad=True,
    merge_length_s=15,
)
print("识别结果:", res)
