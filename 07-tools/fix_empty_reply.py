"""修两个问题：
1) 空回复气泡（只有「—— xiaohui-r5」）
2) 听不懂时不乱答：短指令没匹配到就给澄清话术
3) 补充口语动作词（起来/起立 等）
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CON = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = CON.read_text(encoding="utf-8")

# ---------- 1) 补充口语动作词 ----------
old_words = '''    "站起来": "stand", "起身": "stand", "站立": "stand",'''
new_words = '''    "站起来": "stand", "起身": "stand", "站立": "stand", "起来": "stand", "起立": "stand",'''
if old_words in c:
    c = c.replace(old_words, new_words, 1)
    print("已补充动作词：起来/起立")

# ---------- 2) 空回复兜底 + 短指令澄清 ----------
if "_clarify_reply" not in c:
    helper = '''

CLARIFY_REPLY = "我没太听清，你是想让我做个动作吗？可以说「站起来」「坐下」「红灯」这种。"


def _clarify_reply(text: str) -> str:
    """短指令但没识别到意图时，给一句澄清而不是让模型瞎猜。"""
    t = (text or "").strip()
    if 1 <= len(t) <= 5:
        return CLARIFY_REPLY
    return ""
'''
    idx = c.find("def _device_cmd_from_text")
    if idx > 0:
        c = c[:idx] + helper.strip() + "\n\n\n" + c[idx:]
        print("已加澄清话术")

CON.write_text(c, encoding="utf-8")
ast.parse(c)

# ---------- 3) chat 返回前兜底 ----------
lines = c.split("\n")
target = None
for i, ln in enumerate(lines):
    if "_strip_model_tag" in ln and "return" in ln:
        target = i
        break

if target is None:
    # 找 chat 里最终返回处
    for i, ln in enumerate(lines):
        if "return {\"reply\":" in ln and i > 1200:
            target = i
            break

print("兜底插入位置:", (target or -1) + 1)
if target:
    indent = " " * (len(lines[target]) - len(lines[target].lstrip()))
    block = [
        indent + "# 空回复兜底：不让气泡只剩模型名",
        indent + "try:",
        indent + "    if not str(reply or '').strip():",
        indent + "        reply = '我没听清，能再说一遍吗？'",
        indent + "except Exception:",
        indent + "    pass",
    ]
    lines[target:target] = block
    c = "\n".join(lines)
    CON.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("已加空回复兜底")

# ---------- 4) 页面：跳过空消息渲染 ----------
P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
p = P.read_text(encoding="utf-8")
if "function xhCleanText" not in p:
    js = '''
  // 去掉模型标签，判断是否为真内容；空内容不渲染气泡
  function xhCleanText(s) {
    return String(s || '').replace(/——\\s*[\\w.\\-:]+/g, '').trim();
  }
'''
    p = p.replace("</script>", js + "\n</script>", 1)
    P.write_text(p, encoding="utf-8")
    print("页面：已加文本清洗函数")
