"""聊天页：重新加入 7 个默认动作按钮（前进/后退/左转/右转/坐下/趴下/跳舞）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if 'data-a="walk"' in t:
    print("按钮已存在")
    sys.exit(0)

block = '''  <h2>动作控制</h2>
  <div class="acts">
    <button data-a="walk">前进</button>
    <button data-a="back">后退</button>
    <button data-a="left">左转</button>
    <button data-a="right">右转</button>
    <button data-a="sit">坐下</button>
    <button data-a="lie">趴下</button>
    <button data-a="dance">跳舞</button>
  </div>

'''

anchor = '  <h2>舵机微调</h2>'
if anchor in t:
    t = t.replace(anchor, block + anchor, 1)
    F.write_text(t, encoding="utf-8")
    print("已加入 7 个默认动作按钮")
else:
    print("⚠ 未找到插入位置")
