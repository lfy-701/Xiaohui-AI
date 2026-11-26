"""修复 handle_say：先用 TTS 合成到文件，再转 Opus 帧推送。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

start = end = None
for i, ln in enumerate(lines):
    if start is None and "data = await audio_to_data(text, True)" in ln:
        start = i - 1  # 保留 try 后一行空行位置
    if start is not None and "if not packets:" in ln:
        end = i
        break

if start is None or end is None:
    print("⚠ 未找到替换区间")
    sys.exit(1)

indent = " " * 12
new = [
    indent + "# 先合成到临时文件，再转 Opus",
    indent + "import os as _os",
    indent + "import tempfile as _tf",
    indent + "",
    indent + "_tmp = _tf.NamedTemporaryFile(suffix='.mp3', delete=False)",
    indent + "_tmp.close()",
    indent + "_path = getattr(tts, 'audio_file_path', '') or _tmp.name",
    indent + "_res = await tts.text_to_speak(text, _path)",
    indent + "if isinstance(_res, str) and _os.path.exists(_res):",
    indent + "    _path = _res",
    indent + "if not _os.path.exists(_path):",
    indent + "    return self._respond({'ok': False, 'error': 'TTS 未生成音频'}, 500)",
    indent + "data = await audio_to_data(_path, True)",
    indent + "packets = list(data or [])",
    indent + "try:",
    indent + "    _os.unlink(_tmp.name)",
    indent + "except Exception:",
    indent + "    pass",
    "",
]
lines[start:end] = new
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已改为先合成再转码；语法 OK")
