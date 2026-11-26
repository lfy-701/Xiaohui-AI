"""预生成唤醒应答音频（我在，你说。），写入唤醒词缓存，避免首次唤醒无声/延迟。"""
import asyncio
import hashlib
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
TEXT = "我在，你说。"
VOICE = "zh-CN-YunjianNeural"

dst_dir = VS / "config" / "assets" / "wakeup_words"
dst_dir.mkdir(parents=True, exist_ok=True)

key = hashlib.md5(VOICE.encode()).hexdigest()
mp3 = dst_dir / f"{key}.mp3"

import edge_tts


async def synth():
    comm = edge_tts.Communicate(TEXT, voice=VOICE, rate="+10%")
    await comm.save(str(mp3))


asyncio.run(synth())
size = mp3.stat().st_size
print(f"  已生成 {mp3.name}  {size/1024:.1f} KB")

# 写入唤醒词缓存 yaml
cfg = VS / "data" / ".wakeup_words.yaml"
entry = f"""{key}:
  file_path: config/assets/wakeup_words\\{key}.mp3
  text: {TEXT}
  time: {time.time()}
  voice: {VOICE}
"""

existing = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
# 去掉旧的同 key 段
lines = existing.splitlines()
out, skip = [], False
for ln in lines:
    if ln.startswith(key + ":"):
        skip = True
        continue
    if skip and (ln.startswith("  ") or ln == ""):
        continue
    skip = False
    out.append(ln)

cfg.write_text("\n".join(out).rstrip("\n") + "\n" + entry, encoding="utf-8")
print(f"  已写入缓存 {cfg.name}")
print("  完成")
