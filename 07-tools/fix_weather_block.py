"""修复插入位置导致的缩进错误：把天气分支移到日期分支之后。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
lines = P.read_text(encoding="utf-8").split("\n")

# 删除坏掉的天气块（4 行 + 后面的 pass 顺序错乱）
out = []
skip = False
for i, ln in enumerate(lines):
    if "# 天气直接查 Open-Meteo，避免模型编温度" in ln:
        skip = True
        continue
    if skip:
        if ln.strip() == "pass" and i > 0 and lines[i - 1].strip() == "pass":
            skip = False
        continue
    out.append(ln)

lines = out

# 在日期分支的 except 后补 pass，并插入正确的天气块
target = None
for i, ln in enumerate(lines):
    if "'model': 'date'" in ln:
        target = i
        break

if target is None:
    print("⚠ 未找到日期分支")
    sys.exit(1)

# 找到日期 try/except 的结束（下一个非缩进行）
end = target
indent_len = 4
while end + 1 < len(lines):
    nxt = lines[end + 1]
    cur = len(nxt) - len(nxt.lstrip())
    if nxt.strip() and cur <= indent_len:
        break
    end += 1

block = [
    "    # 天气直接查 Open-Meteo，避免模型编温度",
    "    try:",
    "        _w_reply = _weather_answer(str(getattr(body, 'text', '') or ''))",
    "        if _w_reply:",
    "            return {'reply': _w_reply, 'model': 'weather', 'session_id': (getattr(body, 'session_id', '') or '')}",
    "    except Exception:",
    "        pass",
    "",
]

lines[end + 1:end + 1] = block
P.write_text("\n".join(lines), encoding="utf-8")
ast.parse(P.read_text(encoding="utf-8"))
print("已修复并插入天气分支（行", end + 2, "）")
