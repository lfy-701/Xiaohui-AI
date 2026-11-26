"""撤回音乐伴舞（摇尾巴 + 彩灯）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

out = []
skip = False
removed = 0
for i, ln in enumerate(lines):
    if ln.startswith("async def _music_vibe"):
        skip = True
    if skip:
        removed += 1
        if ln.strip() == "" and i > 0 and lines[i - 1].strip() == "":
            skip = False
        continue
    if "_vibe_stop" in ln or "_vibe_task" in ln:
        removed += 1
        continue
    if ln.strip() == "_vibe_stop.set()":
        removed += 1
        continue
    out.append(ln)

# 清理孤立的三行 try/except/pass
clean = []
i = 0
while i < len(out):
    if (out[i].strip() == "try:" and i + 2 < len(out)
            and out[i + 1].strip() == "except Exception:"
            and out[i + 2].strip() == "pass"):
        i += 3
        removed += 3
        continue
    clean.append(out[i])
    i += 1

F.write_text("\n".join(clean), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print(f"已撤回伴舞，删除 {removed} 行；语法 OK")
print("残留:", "有" if "_music_vibe" in F.read_text(encoding="utf-8") else "无")
