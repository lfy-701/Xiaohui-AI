"""按方案 B：占住会话，边推边播，推完再 stop（保持会话存活到播放结束）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

# 找一行一次性推送 FIRST 的位置
idx = None
for i, ln in enumerate(lines):
    if "SentenceType.FIRST, packets," in ln:
        idx = i
        break
if idx is None:
    print("⚠ 未找到一次性推送行")
    sys.exit(1)

indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
pad = indent
new_block = [
    pad + "# 方案 B：先发 tts start 占住会话，再按 55ms/帧匀速推（略快于播放，持续有缓冲）",
    pad + 'await _tts_msg(conn, "start")',
    pad + "conn.client_abort = False",
    pad + 'await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")',
    pad + "await asyncio.sleep(0.05)",
    pad + "_i = 3",
    pad + "while _i < len(packets):",
    pad + '    if getattr(conn, "client_abort", False):',
    pad + "        break",
    pad + "    await sendAudioMessage(conn, SentenceType.MIDDLE, packets[_i:_i + 1], None)",
    pad + "    _i += 1",
    pad + "    await asyncio.sleep(0.055)",
    pad + "sent = _i",
    pad + "await asyncio.sleep(0.3)",
    pad + 'await sendAudioMessage(conn, SentenceType.LAST, [], None)',
    pad + 'await _tts_msg(conn, "stop")',
]

# 替换：从 idx 开始到 sent = len(packets) 行（含）
end = idx
while end < len(lines) and "sent = len(packets)" not in lines[end]:
    end += 1

out = lines[:idx] + new_block + lines[end + 1:]
F.write_text("\n".join(out), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已改为方案 B：占住会话 + 匀速推送")
