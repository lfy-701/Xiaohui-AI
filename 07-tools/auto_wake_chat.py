"""B 方案：网页发送时自动唤醒设备并让它念回复。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = F.read_text(encoding="utf-8")

if "xhEnsureDevice" in t:
    print("已存在")
    sys.exit(0)

# 1) 新增自动唤醒函数（放在 xhSay 之前）
helper = '''
  // 确保设备处于连接状态；未连接则下发 connect 并等待
  async function xhEnsureDevice(timeoutMs) {
    const limit = timeoutMs || 12000;
    const t0 = Date.now();
    try {
      const st = await (await fetch('/api/console/status')).json();
      if (st && st.count > 0) return true;
    } catch (e) {}
    try {
      await fetch('/api/device/push', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'connect'})
      });
    } catch (e) { return false; }
    add('… 正在唤醒设备', 'sys');
    while (Date.now() - t0 < limit) {
      await new Promise(r => setTimeout(r, 600));
      try {
        const st = await (await fetch('/api/console/status')).json();
        if (st && st.count > 0) return true;
      } catch (e) {}
    }
    return false;
  }

'''
anchor = "  async function xhSay(text)"
if anchor in t:
    t = t.replace(anchor, helper + anchor, 1)
else:
    t = t.replace("</script>", helper + "\n</script>", 1)

# 2) 发送流程里自动唤醒 + 播报
old = '''      const reply = d.reply || d.content || d.text || '(没有回复)';
      add(reply, 'bot');
      if (window.xhSay) xhSay(reply.slice(0, 200));'''
new = '''      const reply = d.reply || d.content || d.text || '(没有回复)';
      add(reply, 'bot');
      // 自动唤醒设备，再让它念出来（不需要手动点唤醒）
      if (window.xhEnsureDevice && window.xhSay) {
        const okDev = await xhEnsureDevice(12000);
        if (okDev) {
          xhSay(reply.slice(0, 200));
        } else {
          add('… 设备没连上，这句只在网页显示', 'sys');
        }
      }'''

if old in t:
    t = t.replace(old, new, 1)
else:
    print("⚠ 未匹配发送流程")

F.write_text(t, encoding="utf-8")
print("已加自动唤醒与播报")
