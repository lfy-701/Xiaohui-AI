"""撤回屏幕状态提示。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")

# 1) 撤 sendAudioHandle 里的提示与 helper
S = VS / "core" / "handle" / "sendAudioHandle.py"
s = S.read_text(encoding="utf-8")

s = s.replace('''
    # 说完这一轮：屏幕上提示轮到用户（只在 stop 时）
    if state == "stop":
        try:
            await send_display_text(conn, "🎤 轮到你说啦")
        except Exception:
            pass''', "")

idx = s.find("\n\nasync def send_display_text")
if idx > 0:
    s = s[:idx].rstrip() + "\n"

S.write_text(s, encoding="utf-8")
ast.parse(s)
print("sendAudioHandle：提示与 helper 已移除")

# 2) 撤 mcp_executor 里的提示
M = VS / "core" / "providers" / "tools" / "device_mcp" / "mcp_executor.py"
m = M.read_text(encoding="utf-8")
m = m.replace('''# 屏幕提示：正在调用工具（不朗读、不影响音频）
try:
    from core.handle.sendAudioHandle import send_display_text, send_emotion
    await send_display_text(conn, '🔍 正在查询…')
    await send_emotion(conn, 'neutral')
except Exception:
    pass
''', "")
M.write_text(m, encoding="utf-8")
ast.parse(m)
print("mcp_executor：提示已移除")
print("残留:", "有" if ("send_display_text" in S.read_text(encoding='utf-8') or "send_display_text" in m) else "无")
