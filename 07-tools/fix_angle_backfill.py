"""修复角度回填：直接用 xhAngles 并重绘滑块。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

old = """    // 把该动作当前角度显示到滑块上（已自定义优先，其次固件默认）
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
    }"""

new = """    // 把该动作当前角度显示到舵机微调滑块上（已自定义优先，其次固件默认）
    const src = window.__xhOverrides[key] || (XH_ACTION_ANGLES[key] || []).join(',');
    if (src) {
      const arr = String(src).split(',').map(function (x) { return parseInt(x) || 90; });
      for (let i = 0; i < 4 && i < arr.length; i++) {
        xhAngles[i] = arr[i];
      }
      xhRenderServos();          // 重绘滑块，角度立即显示出来
      fetch('/api/device/pose', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({angles: xhAngles.join(',')})
      }).catch(function () {});
      add('▸ 「' + (XH_ACTION_LABELS[key] || key) + '」当前角度：' + arr.join(', '), 'sys');
    }"""

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    print("已修复：改用 xhAngles 并重绘滑块")
else:
    print("⚠ 未匹配回填代码")

# 保存时也用 xhAngles
t2 = F.read_text(encoding="utf-8")
if "window.xhAngles.join(',')" in t2:
    t2 = t2.replace("window.xhAngles.join(',')", "xhAngles.join(',')")
    F.write_text(t2, encoding="utf-8")
    print("保存逻辑已同步修正")
