"""短指令没识别到意图时，给澄清而不是让模型瞎答。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
lines = P.read_text(encoding="utf-8").split("\n")

# 找设备指令拦截块，在其后追加澄清判断
target = None
for i, ln in enumerate(lines):
    if "if _push_device_cmd(_kind, _val):" in ln:
        target = i
        break

if target is None:
    print("⚠ 未找到拦截块")
    sys.exit(1)

# 找到该 if 块的结尾（下一行同缩进的 return）
end = target
indent_len = len(lines[target]) - len(lines[target].lstrip())
for j in range(target + 1, min(target + 10, len(lines))):
    cur = len(lines[j]) - len(lines[j].lstrip())
    if cur < indent_len and lines[j].strip():
        end = j
        break

patch = [
    " " * indent_len + "# 短指令但没匹配到意图：澄清，不让模型瞎猜",
    " " * indent_len + "if 1 <= len(_txt.strip()) <= 5 and not any(ch in _txt for ch in '?？吗呢啊') :",
    " " * (indent_len + 4) + "return {'reply': '我没太听清，你是想让我做动作还是开灯？可以说「站起来」或「红灯」。',",
    " " * (indent_len + 5) + "'model': 'clarify', 'session_id': ''}",
]

if "model': 'clarify'" not in "\n".join(lines):
    lines[end:end] = patch
    P.write_text("\n".join(lines), encoding="utf-8")
    ast.parse(P.read_text(encoding="utf-8"))
    print("已加澄清分支（行", end + 1, "）")
else:
    print("已存在")
