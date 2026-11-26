"""修正打字拦截里 body 的取值方式（pydantic 对象不是 dict）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = p.read_text(encoding="utf-8")

old = "        _kind, _val, _say = _device_cmd_from_text(str((body or {}).get('text') or ''))"
new = (
    "        _txt = getattr(body, 'text', '') if not isinstance(body, dict) else (body.get('text') or '')\n"
    "        _kind, _val, _say = _device_cmd_from_text(str(_txt or ''))"
)

if old in t:
    t = t.replace(old, new, 1)
    t = t.replace("'session_id': (body or {}).get('session_id') or ''}",
                  "'session_id': (getattr(body, 'session_id', '') or '')}")
    p.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已修正 body 取值")
else:
    print("⚠ 未匹配，可能是缩进不同")
    for i, ln in enumerate(t.split("\n")):
        if "_device_cmd_from_text(" in ln:
            print("  L%d: %s" % (i + 1, ln))
