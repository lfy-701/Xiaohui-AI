"""把噪声过滤接到 detect 分支（按真实缩进匹配）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\textHandle.py")
t = P.read_text(encoding="utf-8")

if "_is_junk_text(original_text)" in t:
    print("已接入，无需重复")
    sys.exit(0)

old = '''                if "text" in msg_json:
                    original_text = msg_json["text"]  # 保留原始文本
                    filtered_len, filtered_text = remove_punctuation_and_length('''

new = '''                if "text" in msg_json:
                    original_text = msg_json["text"]  # 保留原始文本
                    if _is_junk_text(original_text):
                        conn.logger.bind(tag=TAG).info(
                            f"忽略无效识别: {original_text!r}"
                        )
                        await send_tts_message(conn, "stop", None)
                        conn.client_is_speaking = False
                        return
                    filtered_len, filtered_text = remove_punctuation_and_length('''

if old in t:
    t = t.replace(old, new, 1)
    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已接入 detect 分支；语法 OK")
else:
    print("⚠ 未匹配")
