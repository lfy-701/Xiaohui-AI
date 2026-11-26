"""ASR 噪声过滤：写入 textHandle 并接入 detect 分支。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\textHandle.py")
t = P.read_text(encoding="utf-8")

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

if "_is_junk_text" not in t:
    lines = t.split("\n")
    last_import = max(
        i for i, ln in enumerate(lines)
        if ln.startswith("import ") or ln.startswith("from ")
    )
    lines.insert(last_import + 1, HELPER)
    t = "\n".join(lines)

old = '''                    if "text" in msg_json:
                        original_text = msg_json["text"]  # 保留原始文本'''

new = '''                    if "text" in msg_json:
                        original_text = msg_json["text"]  # 保留原始文本
                        if _is_junk_text(original_text):
                            conn.logger.bind(tag=TAG).info(
                                f"忽略无效识别: {original_text!r}"
                            )
                            await send_tts_message(conn, "stop", None)
                            conn.client_is_speaking = False
                            return'''

if old in t and "_is_junk_text(original_text)" not in t:
    t = t.replace(old, new, 1)
    print("已接入 detect 分支")

P.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
