"""语音词表精确回退到扩展前（只保留 sit/lie/dance/stand/walk/back/left/right/wag/shake/stop）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
lines = V.read_text(encoding="utf-8").split("\n")

start = next(i for i, ln in enumerate(lines) if ln.strip() == "actions = {")
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "}")

indent = " " * (len(lines[start + 1]) - len(lines[start + 1].lstrip()))
original = [
    "actions = {",
    f'{indent}"坐下": "sit", "坐": "sit",',
    f'{indent}"趴下": "lie", "趴": "lie",',
    f'{indent}"跳舞": "dance",',
    f'{indent}"站起来": "stand", "起身": "stand",',
    f'{indent}"前进": "walk", "往前走": "walk",',
    f'{indent}"后退": "back", "往后退": "back",',
    f'{indent}"左转": "left", "右转": "right",',
    f'{indent}"摇尾巴": "wag", "摇摇头": "shake",',
    f'{indent}"停下": "stop",',
    "}",
]
lines[start:end + 1] = original
text = "\n".join(lines)
V.write_text(text, encoding="utf-8")
ast.parse(text)
print("语音词表已回退到扩展前（11 个动作）")
