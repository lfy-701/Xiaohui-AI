"""按行号在「音乐」tab 后插入大模型专区链接。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
lines = P.read_text(encoding="utf-8").split("\n")

if any("大模型专区" in ln for ln in lines):
    print("入口已存在")
    sys.exit(0)

idx = None
for i, ln in enumerate(lines):
    if 'data-tab="music"' in ln:
        idx = i
        break

if idx is None:
    print("⚠ 未找到音乐 tab")
    sys.exit(1)

lines.insert(
    idx + 1,
    '        <a class="tab" href="http://100.100.221.34:8013/" target="_blank" '
    'rel="noreferrer" style="text-decoration:none" '
    'title="大模型专区（DeepSeek 云端）">大模型专区</a>',
)
P.write_text("\n".join(lines), encoding="utf-8")
print("已在第", idx + 2, "行插入入口")
