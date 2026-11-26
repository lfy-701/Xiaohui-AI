"""ASR 失败点定位 v2：绕开 CaptureOutput，直接测 FunASR.generate 的入参形态。"""
import faulthandler
import math
import os
import struct
import sys
import traceback

faulthandler.enable()
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


def pcm_sine(rate=16000, seconds=1.0):
    pcm = b""
    for i in range(int(rate * seconds)):
        v = int(12000 * math.sin(2 * math.pi * 220 * i / rate))
        pcm += struct.pack("<h", v)
    return pcm


def main():
    from funasr import AutoModel

    print("[1] 加载模型 …", flush=True)
    model = AutoModel(
        model="models/SenseVoiceSmall",
        vad_kwargs={"max_single_segment_time": 30000},
        disable_update=True,
        hub="hf",
    )
    print("[1] ok", flush=True)

    valid = pcm_sine()
    print(f"[2] 有效 PCM {len(valid)} 字节", flush=True)
    try:
        r = model.generate(input=valid, cache={}, language="zh", use_itn=True, batch_size_s=60)
        print("[2] ok ->", str(r)[:200], flush=True)
    except Exception as e:
        print(f"[2] 失败 {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()

    print("[3] 空 PCM b''", flush=True)
    try:
        r = model.generate(input=b"", cache={}, language="zh", use_itn=True, batch_size_s=60)
        print("[3] ok ->", str(r)[:200], flush=True)
    except Exception as e:
        print(f"[3] 失败 {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
