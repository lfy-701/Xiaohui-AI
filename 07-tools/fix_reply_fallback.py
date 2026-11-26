"""在 chat 接口返回前加空回复兜底；清理数据库里的空消息。"""
import ast
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
lines = P.read_text(encoding="utf-8").split("\n")

# 找 chat 接口定义
start = None
for i, ln in enumerate(lines):
    if '"/api/agents/{agent_id}/chat"' in ln:
        start = i
        break
if start is None:
    print("⚠ 未找到 chat 接口")
    sys.exit(1)

# 在函数体内找第一处 return（chat 的最终返回）
fn = None
for i in range(start, min(start + 10, len(lines))):
    if lines[i].lstrip().startswith("def "):
        fn = i
        break

ret = None
for i in range(fn or start, min((fn or start) + 120, len(lines))):
    if lines[i].strip().startswith("return") and "reply" in lines[i]:
        ret = i
        break

if ret is None:
    print("⚠ 未找到返回语句")
    sys.exit(1)

if "# 空回复兜底" not in "\n".join(lines):
    indent = " " * (len(lines[ret]) - len(lines[ret].lstrip()))
    block = [
        indent + "# 空回复兜底：避免气泡只剩模型名",
        indent + "if not str(locals().get('reply', '') or '').strip():",
        indent + "    reply = '我没听清，能再说一遍吗？'",
    ]
    lines[ret:ret] = block
    P.write_text("\n".join(lines), encoding="utf-8")
    ast.parse(P.read_text(encoding="utf-8"))
    print("已插入空回复兜底（行", ret + 1, "）")
else:
    print("兜底已存在")

# 清理数据库空消息
db = r"D:\AI-Companion-shared\xiaohui-ai\console\data\console.db"
con = sqlite3.connect(db)
cols = [r[1] for r in con.execute("PRAGMA table_info(messages)")] if con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'").fetchone() else []
print("messages 表列:", cols)
if cols:
    before = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    con.execute("DELETE FROM messages WHERE content IS NULL OR TRIM(content)='' OR content LIKE '%——%'")
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    print(f"清理空/带标签消息：{before} → {after}")
con.close()
