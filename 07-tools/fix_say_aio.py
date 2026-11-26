"""修复 handle_say：改用 audio_to_data（避免 async for 误用）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

start = end = None
for i, ln in enumerate(lines):
    if start is None and "if hasattr(tts," in ln:
        start = i
    if start is not None and "if not packets:" in ln:
        end = i
        break

if start is None or end is None:
    print("⚠ 未找到替换区间")
    sys.exit(1)

indent = " " * 12
new = [
    indent + "data = await audio_to_data(text, True)",
    indent + "packets = list(data or [])",
    "",
]
lines[start:end] = new
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已改为 audio_to_data；语法 OK")
