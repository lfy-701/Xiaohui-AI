"""修复被写坏的分发代码块（缩进错乱）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
lines = F.read_text(encoding="utf-8").split("\n")

start = end = None
for i, ln in enumerate(lines):
    if "# 首先进行意图分析" in ln:
        start = i
    if start is not None and "# 意图未被处理，继续常规聊天流程" in ln:
        end = i
        break
if start is None or end is None:
    print("⚠ 未找到区间")
    sys.exit(1)

BLOCK = [
    "    # 天气/新闻直通：优先于意图处理，由我们自己播报（整句、不分段）",
    "    try:",
    "        if await _handle_query_cmd(conn, text):",
    "            return",
    "    except Exception as e:",
    "        conn.logger.bind(tag=TAG).warning(f\"查询直通异常: {e}\")",
    "",
    "    # 首先进行意图分析",
    "    intent_handled = await handle_user_intent(conn, text)",
    "",
    "    if intent_handled:",
    "        # 如果意图已被处理，不再进行聊天",
    "        return",
    "",
]
lines[start:end] = BLOCK
F.write_text("\n".join(lines), encoding="utf-8")

t = F.read_text(encoding="utf-8")
ast.parse(t)
print("已修复分发块；语法 OK")

# 检查后面设备指令块是否有残留的孤立 return
idx = t.find("# 点歌意图直通")
print("--- 点歌区块预览 ---")
print("\n".join(t[idx:idx + 500].split("\n")[:18]))
