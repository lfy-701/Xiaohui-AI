"""ASR 失败点定位：分离 decode_opus / FunASR.generate 两步。

用法：语音服务 venv 的 python 运行
    .venv\\Scripts\\python.exe asr_probe.py
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

CFG = {"model_dir": "models/SenseVoiceSmall", "output_dir": "tmp/"}


def make_opus_frames(rate=16000, seconds=1.0):
    import opuslib_next as opus
    import math
    import struct

    enc = opus.Encoder(rate, 1, opus.APPLICATION_AUDIO)
    frame = 960  # 60ms @16k
    pcm = b""
    for i in range(int(rate * seconds)):
        v = int(12000 * math.sin(2 * math.pi * 220 * i / rate))
        pcm += struct.pack("<h", v)
    frames = []
    for i in range(0, len(pcm), frame * 2):
        chunk = pcm[i:i + frame * 2]
        if len(chunk) < frame * 2:
            chunk = chunk + b"\x00" * (frame * 2 - len(chunk))
        frames.append(enc.encode(chunk, frame))
    return frames


def main():
    from core.providers.asr.fun_local import ASRProvider

    print("[1] 加载模型 …", flush=True)
    prov = ASRProvider(CFG, True)
    print("[1] ok", flush=True)

    frames = make_opus_frames()
    print(f"[2] 合成 opus 帧 {len(frames)} 个", flush=True)

    pcm_list = prov.decode_opus(frames)
    print(f"[2] decode_opus -> {len(pcm_list)} 段, 总字节 {sum(len(x) for x in pcm_list)}", flush=True)

    joined = b"".join(pcm_list)
    print(f"[3] generate(有效PCM {len(joined)} 字节) …", flush=True)
    try:
        res = prov.model.generate(input=joined, cache={}, language="zh",
                                  use_itn=True, batch_size_s=60)
        print("[3] ok ->", str(res)[:200], flush=True)
    except Exception as e:
        print(f"[3] 失败: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()

    print("[4] generate(b'') …", flush=True)
    try:
        res = prov.model.generate(input=b"", cache={}, language="zh",
                                  use_itn=True, batch_size_s=60)
        print("[4] ok ->", str(res)[:200], flush=True)
    except Exception as e:
        print(f"[4] 失败: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
