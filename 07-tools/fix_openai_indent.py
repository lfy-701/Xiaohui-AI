"""修复混合路由插入导致的缩进错乱：
把 helper 移到类外（模块级），并把 response 重新放回类里。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
lines = F.read_text(encoding="utf-8").split("\n")

# 1) 找到 helper 块（从「混合路由」注释到 response 之前）
helper_start = next(i for i, ln in enumerate(lines) if "混合路由" in ln and ln.startswith("#"))
resp_idx = next(i for i, ln in enumerate(lines) if ln.startswith("    def response(self, session_id"))
# response 前有空行与可能的重复
helper_end = resp_idx
while helper_end > 0 and not lines[helper_end - 1].strip():
    helper_end -= 1

helper_block = lines[helper_start:helper_end]
del lines[helper_start:helper_end]

# 2) 把 helper 插到 class 之前
cls = next(i for i, ln in enumerate(lines) if ln.startswith("class LLMProvider"))
lines[cls:cls] = helper_block + ["", ""]

# 3) 把 response 缩进回类里（4 空格），直到 response_with_functions
r_idx = next(i for i, ln in enumerate(lines) if ln.startswith("    def response(self, session_id"))
end_idx = next(i for i, ln in enumerate(lines) if ln.startswith("    def response_with_functions"))

for i in range(r_idx, end_idx):
    if lines[i].strip():
        lines[i] = "    " + lines[i]

F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已修复：helper 移到模块级，response 归位类内；语法 OK")
