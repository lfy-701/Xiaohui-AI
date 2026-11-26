"""打字唤醒：输入唤醒词时让设备先应一声，再进入对话。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
h = F.read_text(encoding="utf-8")

if "xhWakeByText" in h:
    print("已存在")
    sys.exit(0)

js = '''
  // ---------------- 打字唤醒 ----------------
  // 输入唤醒词时：让设备应一声，并把后续输入当作对话
  const WAKE_WORDS = ['你好小慧', '小慧小慧', '嘿小慧', '小慧'];
  let wokeAt = 0;

  function isWakeText(t) {
    const s = (t || '').replace(/[\\s，。！？,.!?]/g, '');
    return WAKE_WORDS.some(w => s === w || s === w + '小慧');
  }

  async function xhWakeByText() {
    add('▸ 唤醒：你好小慧', 'sys');
    const r = await xhSay('嗯，我在呢，你说。');
    if (r && r.ok) {
      wokeAt = Date.now();
      add('✓ 设备已唤醒，可以直接说话或打字', 'sys ok');
    } else {
      add('✗ 唤醒失败：' + ((r && r.error) || '设备未连接'), 'sys err');
    }
  }
  window.xhWakeByText = xhWakeByText;
'''

anchor = "  // 让设备把这句话说出来（需要设备在线）"
if anchor in h:
    h = h.replace(anchor, js + "\n" + anchor, 1)
else:
    h = h.replace("</script>", js + "\n</script>", 1)

# 发送时先判断是不是唤醒词
old = """  async function send() {
    const text = input.value.trim();
    if (!text) return;"""
new = """  async function send() {
    const text = input.value.trim();
    if (!text) return;
    if (isWakeText(text)) {
      input.value = '';
      add(text, 'me');
      await xhWakeByText();
      return;
    }"""
if old in h:
    h = h.replace(old, new, 1)
    print("已接入唤醒判断")
else:
    print("⚠ send 函数锚点不匹配")

F.write_text(h, encoding="utf-8")
print("完成")
