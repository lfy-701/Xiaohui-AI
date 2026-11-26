"""在设备 MCP 执行器里插入「正在查询」屏幕提示。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\tools\device_mcp\mcp_executor.py")
lines = p.read_text(encoding="utf-8").split("\n")

# 找 "args_str = json.dumps" 行，在其前插入提示
idx = None
for i, ln in enumerate(lines):
    if "args_str = json.dumps" in ln:
        idx = i
        break

if idx is None:
    print("⚠ 未找到插入点")
    sys.exit(1)

indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
block = [
    indent + "# 屏幕提示：正在调用工具（不朗读、不影响音频）",
    indent + "try:",
    indent + "    from core.handle.sendAudioHandle import send_display_text, send_emotion",
    indent + "    await send_display_text(conn, '🔍 正在查询…')",
    indent + "    await send_emotion(conn, 'neutral')",
    indent + "except Exception:",
    indent + "    pass",
]

lines[idx:idx] = block
p.write_text("\n".join(lines), encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("已插入工具调用屏幕提示")
