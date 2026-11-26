"""动作编辑：滑块实时控制舵机（MCP 直发 + 节流）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\actions.html")
h = F.read_text(encoding="utf-8")

if "xhLiveSend" in h:
    print("已存在")
    sys.exit(0)

# 1) 滑块事件改为实时发送
h = h.replace("""             oninput="onSlide(${i}, this.value)">""",
              """             oninput="onSlide(${i}, this.value)"
             onchange="xhFlush(${i})">""")

# 2) 插入实时发送逻辑
js = '''
// ---------------- 实时控制 ----------------
// 拖动时把变化节流发送：同一路舵机只发最新值，最多 8 次/秒
const xhPending = {};
const xhTimer = {};
const xhLastSent = {};

async function xhSendServo(idx, angle) {
  const now = Date.now();
  if (xhLastSent[idx] && now - xhLastSent[idx] < 120) return;
  xhLastSent[idx] = now;
  try {
    const r = await fetch('/api/console/action', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tool: 'self.set_servo', arguments: {servo: idx, angle: angle}})
    });
    const d = await r.json();
    if (!d.ok) xhFallback(idx, angle);
  } catch (e) {
    xhFallback(idx, angle);
  }
}

// MCP 通道不可用时退回心跳队列（慢一点但一定能到）
async function xhFallback(idx, angle) {
  const ang = angleStr();
  try {
    await fetch('/api/device/pose', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({angles: ang})
    });
  } catch (e) {}
}

function xhLive(idx, angle) {
  xhPending[idx] = angle;
  clearTimeout(xhTimer[idx]);
  xhTimer[idx] = setTimeout(function () {
    if (xhPending[idx] !== undefined) xhSendServo(idx, xhPending[idx]);
  }, 60);   // 60ms 合并抖动，实际约 8 次/秒
}

function xhFlush(idx) {
  clearTimeout(xhTimer[idx]);
  if (xhPending[idx] !== undefined) xhSendServo(idx, xhPending[idx], true);
}

window.xhLive = xhLive;
window.xhFlush = xhFlush;
'''

anchor = "function onSlide(i, v) {"
if anchor in h:
    h = h.replace(anchor, js + "\n" + anchor, 1)
else:
    h = h.replace("</script>", js + "\n</script>", 1)

# 3) onSlide 里触发实时发送
h = h.replace("""function onSlide(i, v) {
  angles[i] = parseInt(v);
  document.getElementById('v' + i).textContent = v + '°';
}""",
"""function onSlide(i, v) {
  angles[i] = parseInt(v);
  document.getElementById('v' + i).textContent = v + '°';
  if (typeof xhLive === 'function') xhLive(i, angles[i]);
}""")

F.write_text(h, encoding="utf-8")
print("已改为实时控制")
