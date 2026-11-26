"""调整动作时，把该动作的角度实时显示到滑块上。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if "XH_ACTION_ANGLES" in t:
    print("已存在")
    sys.exit(0)

# 1) 固件默认角度表（与 servo_controller.cc 一致）
defaults = '''
  // 与固件 servo_controller.cc 一致的默认角度
  const XH_ACTION_ANGLES = {
    stand: [90, 90, 90, 90, 90, 90],
    sit:   [145, 145, 35, 35, 90, 90],
    lie:   [158, 158, 22, 22, 90, 60],
    walk:  [90, 90, 90, 90, 90, 90],
    back:  [90, 90, 90, 90, 90, 90],
    left:  [60, 60, 120, 120, 90, 90],
    right: [120, 120, 60, 60, 90, 90],
    dance: [70, 70, 110, 110, 90, 60]
  };
'''

anchor = "  const XH_ACTION_LABELS = {"
if anchor in t:
    t = t.replace(anchor, defaults.strip() + "\n\n" + anchor, 1)
    print("已加默认角度表")

# 2) xhTuneAction 里把角度灌到滑块
old = '''  function xhTuneAction(key) {
    window.__xhTune = key;
    const bar = document.getElementById('xhTuneBar');
    const nm = document.getElementById('xhTuneName');
    if (nm) nm.textContent = XH_ACTION_LABELS[key] || key;
    if (bar) bar.style.display = 'block';'''

new = '''  function xhTuneAction(key) {
    window.__xhTune = key;
    const bar = document.getElementById('xhTuneBar');
    const nm = document.getElementById('xhTuneName');
    if (nm) nm.textContent = XH_ACTION_LABELS[key] || key;
    if (bar) bar.style.display = 'block';

    // 把该动作当前角度显示到滑块上（已自定义优先，其次固件默认）
    const src = window.__xhOverrides[key] || (XH_ACTION_ANGLES[key] || []).join(',');
    if (src) {
      const arr = String(src).split(',').map(function (x) { return parseInt(x) || 90; });
      for (let i = 0; i < 4 && i < arr.length; i++) {
        window.xhAngles[i] = arr[i];
        const sl = document.getElementById('xhr' + i);
        if (sl) sl.value = arr[i];
        const lb = document.getElementById('xhv' + i);
        if (lb) lb.textContent = arr[i] + '°';
      }
      fetch('/api/device/pose', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({angles: window.xhAngles.join(',')})
      }).catch(function () {});
      add('▸ 当前角度：' + arr.join(', '), 'sys');
    }'''

if old in t:
    t = t.replace(old, new, 1)
    print("调整时已同步显示角度")
else:
    print("⚠ 未匹配 xhTuneAction")

F.write_text(t, encoding="utf-8")
print("完成")
