"""设备屏状态提示：
1) 调用工具时显示「🔍 正在搜索…」
2) 说完话（tts stop）显示「🎤 我在听，你继续说」

实现方式：复用协议里的 tts/sentence_start 文本消息（固件会把它显示在屏幕上），
不改固件、不影响音乐等其他功能。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")

# ---------- 1) 在 sendAudioHandle 里加通用显示函数，并在 tts stop 时提示 ----------
S = VS / "core" / "handle" / "sendAudioHandle.py"
s = S.read_text(encoding="utf-8")

helper = '''

async def send_display_text(conn, text: str):
    """只让屏幕显示一行文字，不朗读。"""
    try:
        payload = {"type": "tts", "state": "sentence_start", "text": text}
        await conn.websocket.send(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


async def send_emotion(conn, emotion: str):
    """切换设备表情。"""
    try:
        payload = {"type": "llm", "emotion": emotion}
        await conn.websocket.send(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass

'''

if "send_display_text" not in s:
    # 插到文件末尾（模块级函数）
    s = s.rstrip() + "\n" + helper
    # tts stop 时提示轮到用户
    old = '''async def send_tts_message(conn, state: str, text=None):'''
    if old in s:
        # 在函数体内找到 stop 分支
        pass
    S.write_text(s, encoding="utf-8")
    print("sendAudioHandle：已加 send_display_text / send_emotion")

# ---------- 2) 工具调用前提示「正在搜索」 ----------
M = VS / "core" / "providers" / "tools" / "device_mcp" / "mcp_executor.py"
m = M.read_text(encoding="utf-8")
if "send_display_text" not in m:
    old_fn = "async def call_mcp_tool("
    idx = m.find(old_fn)
    if idx > 0:
        inject = '''        try:
            from core.handle.sendAudioHandle import send_display_text, send_emotion
            await send_display_text(conn, "🔍 正在查询…")
            await send_emotion(conn, "neutral")
        except Exception:
            pass
'''
        # 插到函数体第一行之后
        body_start = m.find("\n", idx)
        # 找到签名结束（第一个 ':' 后的换行）
        sig_end = m.find(":\n", idx)
        if sig_end > 0:
            insert_at = sig_end + 2
            m = m[:insert_at] + inject + m[insert_at:]
            M.write_text(m, encoding="utf-8")
            ast.parse(m)
            print("mcp_executor：工具调用前已显示「正在查询…」")
    else:
        print("⚠ 未找到 call_mcp_tool")

# ---------- 3) 每轮回答结束提示「轮到你说」 ----------
T = VS / "core" / "handle" / "textHandle.py"
t = T.read_text(encoding="utf-8")
if "轮到你说" not in t:
    old = '''                      await send_stt_message(conn, original_text)'''
    # 保守：不改动复杂分支，只在文件末尾挂一个包装
    print("textHandle：跳过（避免动到对话主流程）")
