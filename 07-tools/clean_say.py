"""清理 handle_say 里残留的分支代码。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

out = []
skip = False
for i, ln in enumerate(lines):
    s = ln.strip()
    # 结束残留块：从 "if not packets:" 前那个多余缩进开始，到 "if not packets:"（同级）
    if s.startswith("if not packets:") and ln.startswith("                if not packets:"):
        skip = True
        continue
    if skip:
        if s.startswith("if not packets:") and ln.startswith("            if not packets:"):
            skip = False
        else:
            continue
    out.append(ln)

F.write_text("\n".join(out), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已清理；语法 OK")
