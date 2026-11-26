"""修复：把 ASR 噪声过滤函数移到文件末尾（之前插到了多行 import 里）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\textHandle.py")
lines = P.read_text(encoding="utf-8").split("\n")

# 1) 删掉坏掉的插入块
start = next(i for i, ln in enumerate(lines) if ln.startswith("_ASR_JUNK"))
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "return False")
del lines[start:end + 1]

text = "\n".join(lines)

HELPER = '''

_ASR_JUNK = {
    "。", "，", "？", "！", ".", ",", "嗯", "啊", "哦", "呃",
    "Yeah.", "Okay.", "はい。", "はい", "Hello.",
}


def _is_junk_text(text: str) -> bool:
    """过滤 ASR 误识别出的空/噪声结果（单字、纯标点、常见语气词）。"""
    s = (text or "").strip()
    if not s:
        return True
    if s in _ASR_JUNK:
        return True
    if all(ch in "。，？！、.,?!~～ " for ch in s):
        return True
    if len(s) == 1 and s not in "坐趴起停走灯":
        return True
    return False
'''

text = text.rstrip() + "\n" + HELPER
P.write_text(text, encoding="utf-8")
ast.parse(text)
print("已把过滤函数移到文件末尾；语法 OK，_is_junk_text 次数:",
      text.count("_is_junk_text"))
