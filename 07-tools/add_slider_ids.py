"""给滑块加 id，便于调整模式回填角度。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

old = """'<input type="range" min="0" max="180" value="' + v + '" ' +"""
new = """'<input type="range" id="xhr' + i + '" min="0" max="180" value="' + v + '" ' +"""

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    print("已给滑块加 id")
else:
    print("⚠ 未匹配滑块模板")
