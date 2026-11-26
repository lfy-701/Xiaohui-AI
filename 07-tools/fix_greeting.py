"""重新生成唤醒词回复音频（小慧版），并更新相关的硬编码文案与唤醒词列表。"""
import asyncio
import subprocess
import sys
from pathlib import Path

import edge_tts

sys.stdout.reconfigure(encoding="utf-8")

SRV = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
GREETING = "你好呀，我是小慧，一直在呢。今天想聊点什么？"
VOICE = "zh-CN-XiaoyiNeural"

mp3 = SRV / "tmp" / "wakeup_xiaohui.mp3"
wav = SRV / "config" / "assets" / "wakeup_words.wav"

async def synth():
    comm = edge_tts.Communicate(GREETING, VOICE)
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch.get("type") == "audio":
                f.write(ch["data"])

asyncio.run(synth())
print("MP3:", mp3.stat().st_size, "bytes")

ffmpeg = SRV / ".venv" / "Scripts" / "ffmpeg.exe"
subprocess.run([str(ffmpeg), "-y", "-loglevel", "error", "-i", str(mp3),
                "-ar", "16000", "-ac", "1", str(wav)], check=True)
print("WAV:", wav.stat().st_size, "bytes")

# 1) 改 helloHandle 的兜底文案
h = SRV / "core" / "handle" / "helloHandle.py"
t = h.read_text(encoding="utf-8")
old = "哈啰啊，我是小智啦，声音好听的台湾女孩一枚，超开心认识你耶，最近在忙啥，别忘了给我来点有趣的料哦，我超爱听八卦的啦"
if old in t:
    t = t.replace(old, GREETING)
    h.write_text(t, encoding="utf-8")
    print("已更新 helloHandle 兜底文案")
else:
    print("文案未找到（可能已改过）")

# 2) 唤醒词列表加入「你好小慧」
c = SRV / "config.yaml"
t = c.read_text(encoding="utf-8")
if '"你好小慧"' not in t:
    t = t.replace('  wakeup_words:\n    - "你好小智"', '  wakeup_words:\n    - "你好小慧"\n    - "你好小智"')
    c.write_text(t, encoding="utf-8")
    print("已把「你好小慧」加入唤醒词列表")
else:
    print("唤醒词列表已包含「你好小慧」")

# 3) 自定义配置里的提示词改成小慧
d = SRV / "data" / ".config.yaml"
t = d.read_text(encoding="utf-8")
if "小小" in t:
    t = t.replace("小小", "小慧")
    d.write_text(t, encoding="utf-8")
    print("已把提示词里的「小小」改为「小慧」")
else:
    print("提示词里没有「小小」")

# 4) 清掉可能存在的旧缓存
cache = SRV / "tmp"
for p in cache.glob("wakeup_words*"):
    if p.name != "wakeup_xiaohui.mp3":
        print("清理缓存:", p.name)
        p.unlink(missing_ok=True)
