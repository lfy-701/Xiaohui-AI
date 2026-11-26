"""服务端也剥离「—— 模型名」后缀，双重保险。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = F.read_text(encoding="utf-8")

if "_strip_model_tag" not in t:
    helper = '''

def _strip_model_tag(text: str) -> str:
    """去掉回复尾部的「—— xiaohui-r3:latest」这类模型标签。"""
    import re as _re

    if not text:
        return text
    out = _re.sub(r"\\s*——\\s*[^\\s]+?:latest\\s*$", "", text, flags=_re.I)
    out = _re.sub(r"\\s*——\\s*[^\\s]+?\\s*$", "", out)
    return out.strip()
'''
    t = t.rstrip() + helper
    F.write_text(t, encoding="utf-8")
    print("已加 _strip_model_tag")

# 在 speak 接口里使用
if "_strip_model_tag(text)" not in t:
    t = F.read_text(encoding="utf-8")
    old = '''    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "缺少 text")
    if not VOICE_HTTP_BASE:'''
    new = '''    text = _strip_model_tag(str((body or {}).get("text") or "").strip())
    if not text:
        raise HTTPException(400, "缺少 text")
    if not VOICE_HTTP_BASE:'''
    if old in t:
        t = t.replace(old, new, 1)
        F.write_text(t, encoding="utf-8")
        print("speak 接口已使用")
    else:
        print("⚠ 未匹配 speak 接口")

ast.parse(F.read_text(encoding="utf-8"))
print("语法 OK")
