"""修复新闻插件：把提示代码移到函数体内部正确位置。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\plugins_func\functions\get_news_from_chinanews.py")
lines = F.read_text(encoding="utf-8").split("\n")

# 1) 删除插在签名中间的坏块
out = []
skip = False
for ln in lines:
    if "# 执行前先告知用户在查询" in ln:
        skip = True
        continue
    if skip:
        if ln.strip() == "pass":
            skip = False
        continue
    out.append(ln)

lines = out

# 2) 找到签名结束（"):" 行）与 docstring 之后插入
sig_end = None
for i, ln in enumerate(lines):
    if ln.startswith("def get_news_from_chinanews("):
        for j in range(i, min(i + 20, len(lines))):
            if lines[j].rstrip().endswith("):"):
                sig_end = j
                break
        break

if sig_end is None:
    print("⚠ 未找到签名结束")
    sys.exit(1)

insert_at = sig_end + 1
if lines[insert_at].strip().startswith('"""'):
    if lines[insert_at].strip().count('"""') < 2:
        j = insert_at + 1
        while j < len(lines) and '"""' not in lines[j]:
            j += 1
        insert_at = j + 1
    else:
        insert_at += 1

BLOCK = [
    "    # 查询前先回应一句（不阻塞）",
    "    try:",
    "        import asyncio as _aio",
    "",
    "        from core.handle.receiveAudioHandle import _speak_ack as _ack_fn",
    "",
    "        _loop = getattr(conn, \"loop\", None)",
    "        if _loop is None:",
    "            _loop = _aio.get_event_loop()",
    "        _aio.run_coroutine_threadsafe(",
    "            _ack_fn(conn, \"正在为您查询，请稍等。\"), _loop",
    "        )",
    "    except Exception:",
    "        pass",
    "",
]

lines[insert_at:insert_at] = BLOCK
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("新闻插件：提示已插到正确位置；语法 OK")
