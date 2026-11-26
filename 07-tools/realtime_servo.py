"""聊天页：删除预置动作，改为自定义动作 + 滑块实时控制舵机。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
lines = F.read_text(encoding="utf-8").split("\n")

# 1) 删除「动作控制」整块
s = e = None
for i, ln in enumerate(lines):
    if s is None and "<h2>动作控制</h2>" in ln:
        s = i
    if s is not None and i > s and "<h2>舵机微调</h2>" in ln:
        e = i
        break
if s is not None and e is not None:
    del lines[s:e]
    print(f"已删除动作控制块（{s+1}~{e} 行）")

t = "\n".join(lines)

# 2) 滑块：拖动即下发（节流 120ms，同一路只发最新值）
old_slide = """  function xhSlide(i, v) {
    xhAngles[i] = parseInt(v);
    const el = document.getElementById('xhv' + i);
    if (el) el.textContent = v + '°';
  }"""
new_slide = """  // 拖动即下发：节流 120ms，只发最新值
  const xhPending = {};
  const xhTimer = {};
  const xhLast = {};

  function xhSlide(i, v) {
    xhAngles[i] = parseInt(v);
    const el = document.getElementById('xhv' + i);
    if (el) el.textContent = v + '°';
    xhPending[i] = xhAngles[i];
    clearTimeout(xhTimer[i]);
    xhTimer[i] = setTimeout(function () {
      xhSendServo(i, xhPending[i]);
    }, 60);
  }

  async function xhSendServo(i, angle) {
    const now = Date.now();
    if (xhLast[i] && now - xhLast[i] < 110) return;
    xhLast[i] = now;
    try {
      const r = await fetch('/api/console/action', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tool: 'self.set_servo', arguments: {servo: i, angle: angle}})
      });
      if (!r.ok) xhServoFallback();
    } catch (e) {
      xhServoFallback();
    }
  }

  // MCP 不可用时退回心跳队列（慢但能到）
  function xhServoFallback() {
    fetch('/api/device/pose', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({angles: xhAngles.join(',')})
    }).catch(function () {});
  }"""

if old_slide in t:
    t = t.replace(old_slide, new_slide, 1)
    print("滑块已改为实时下发")
else:
    print("⚠ 未匹配 xhSlide")

F.write_text(t, encoding="utf-8")
print("完成")
