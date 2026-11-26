"""A+C：唤醒后立刻探活并推送音频，避开设备「播完就断」的时间窗。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if "xhSaySafe" in t:
    print("已存在")
    sys.exit(0)

helper = '''
  // 探活：返回当前语音连接数
  async function xhCount() {
    try {
      const st = await (await fetch('/api/console/status')).json();
      return (st && st.count) || 0;
    } catch (e) { return 0; }
  }

  // 推音频；连接断了就重连一次再推（设备播完就断，要抢时间窗）
  async function xhSaySafe(text) {
    if (!text) return false;
    if ((await xhCount()) > 0) {
      const r = await xhSay(text);
      if (r && r.ok) return true;
    }
    // 重连
    try {
      await fetch('/api/device/push', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'connect'})
      });
    } catch (e) { return false; }
    for (let i = 0; i < 16; i++) {
      await new Promise(r => setTimeout(r, 400));
      if ((await xhCount()) > 0) {
        const r = await xhSay(text);
        return !!(r && r.ok);
      }
    }
    return false;
  }

'''

anchor = "  async function xhSay(text)"
if anchor in t:
    t = t.replace(anchor, helper + anchor, 1)
else:
    t = t.replace("</script>", helper + "\n</script>", 1)

# 发送流程改用 xhSaySafe，且不再等 12 秒
old = '''    // 自动唤醒设备后播报（B 方案）
    if (window.xhEnsureDevice && window.xhSay) {
      const okDev = await xhEnsureDevice(12000);
      if (okDev) { xhSay(reply.slice(0, 200)); }
      else { add('… 设备没连上，这句只在网页显示', 'sys'); }
    } else if (window.xhSay) {
      xhSay(reply.slice(0, 200));
    }'''
new = '''    // 自动唤醒 + 抢时间窗推送（A+C）
    if (window.xhSaySafe) {
      const okDev = await xhSaySafe(reply.slice(0, 200));
      if (!okDev) add('… 设备没连上，这句只在网页显示', 'sys');
    }'''

if old in t:
    t = t.replace(old, new, 1)
    print("已改为 xhSaySafe")
else:
    print("⚠ 未匹配发送流程，尝试宽松替换")
    t = t.replace("const okDev = await xhEnsureDevice(12000);",
                  "const okDev = await (window.xhSaySafe ? xhSaySafe(reply.slice(0, 200)) : xhEnsureDevice(12000));", 1)

# 唤醒词那条路径也换成 xhSaySafe
old2 = '''      const r = await xhSay("嗯，我在呢，你说。");'''
if old2 in t:
    t = t.replace(old2, '''      const r = await xhSaySafe("嗯，我在呢，你说。");''', 1)
    print("唤醒词路径已改")

F.write_text(t, encoding="utf-8")
print("完成")
