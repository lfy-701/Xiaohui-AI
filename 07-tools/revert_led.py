"""撤回灯珠相关改动（控制台 + 语音服务）。"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 控制台 ----------
C = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = C.read_text(encoding="utf-8")

# 1) 移除中间件放行
c = c.replace('''    # 本机语音服务下发灯珠命令
    if path.startswith("/api/device/led"):
        try:
            if request.client and request.client.host in ("127.0.0.1", "::1"):
                return await call_next(request)
        except Exception:
            pass
''', "")

# 2) 移除灯珠文字解析 helper
start = c.find("\nLED_COLORS = {")
if start > 0:
    end = c.find('@app.post("/api/device/led")', start)
    if end > start:
        c = c[:start] + "\n\n" + c[end:]

C.write_text(c, encoding="utf-8")
ast.parse(c)
print("控制台：灯珠放行与解析已移除")

# ---------- 语音服务 ----------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

# 移除整个 _handle_local_cmd 函数
start = v.find("async def _handle_local_cmd(conn, text: str) -> bool:")
end = v.find("async def _handle_music_cmd(conn, text: str) -> bool:")
if start > 0 and end > start:
    v = v[:start] + v[end:]
    print("语音：_handle_local_cmd 已移除")

# 移除调用处
v = v.replace("        if await _handle_local_cmd(conn, text):\n            return\n", "")
v = re.sub(r"[ \t]*if await _handle_local_cmd\(conn, text\):\s*\n[ \t]*return\s*\n", "", v)

V.write_text(v, encoding="utf-8")
ast.parse(v)
print("语音：调用已移除；语法 OK")
print("残留:", "有" if "_handle_local_cmd" in v else "无")
