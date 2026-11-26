"""音乐卡顿优化：降码率 + 预缓冲 + 略快于实时的推送节奏。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

enc_idx = None
first_idx = None
i_idx = None
for i, ln in enumerate(lines):
    if enc_idx is None and "encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)" in ln:
        enc_idx = i
    if first_idx is None and "SentenceType.FIRST, [packets[0]]" in ln:
        first_idx = i
    if i_idx is None and ln.strip() == "i = 1":
        i_idx = i

print("编码器行:", (enc_idx or -1) + 1, "| FIRST 行:", (first_idx or -1) + 1, "| i=1 行:", (i_idx or -1) + 1)

if enc_idx is not None:
    indent = len(lines[enc_idx]) - len(lines[enc_idx].lstrip())
    lines.insert(enc_idx + 1, " " * indent + "encoder.bitrate = 24000  # 降到 24kbps，减半带宽")

if first_idx is not None:
    indent = len(lines[first_idx]) - len(lines[first_idx].lstrip())
    pad = " " * indent
    lines[first_idx] = pad + "# 先灌约 1.8 秒音频，填满设备抖动缓冲"
    lines.insert(first_idx + 1, pad + 'await sendAudioMessage(conn, SentenceType.FIRST, packets[1:31], "")')
    lines.insert(first_idx + 2, pad + "await asyncio.sleep(0.050)")

# 起点改成 31
for i, ln in enumerate(lines):
    if ln.strip() == "i = 1":
        lines[i] = ln.replace("i = 1", "i = 31")
        break

# 节奏略快于实时
for i, ln in enumerate(lines):
    if "await asyncio.sleep(0.120)" in ln:
        lines[i] = ln.replace("0.120", "0.115")

F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已应用：码率 24kbps + 预缓冲 30 帧 + 115ms/2帧")
