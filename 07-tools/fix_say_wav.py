"""修复：mp3 先转 wav（避免 ffprobe 缺失），再转 Opus。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

start = None
for i, ln in enumerate(lines):
    if "data = await audio_to_data(_path, True)" in ln:
        start = i
        break
if start is None:
    print("⚠ 未找到目标行")
    sys.exit(1)

indent = " " * 12
new = [
    indent + "# mp3 → wav（Windows 上 pydub 缺 ffprobe，先转成 wav 再读）",
    indent + "import subprocess as _sp",
    indent + "import imageio_ffmpeg as _iio",
    indent + "_wav = _tmp.name + '.wav'",
    indent + "try:",
    indent + "    _sp.run([_iio.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', _path,",
    indent + "             '-ar', '24000', '-ac', '1', _wav], check=True, timeout=60)",
    indent + "    data = await audio_to_data(_wav, True)",
    indent + "except Exception as _e:",
    indent + "    return self._respond({'ok': False, 'error': f'转码失败: {_e}'}, 500)",
    indent + "packets = list(data or [])",
]
lines[start:start + 2] = new
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已改为 mp3→wav 转码；语法 OK")
