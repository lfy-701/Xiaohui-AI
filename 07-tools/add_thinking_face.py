"""调用 MCP 工具时显示思考表情，开始回答时复原。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")

# ---------- 1) 通用表情发送函数 ----------
S = VS / "core" / "handle" / "sendAudioHandle.py"
s = S.read_text(encoding="utf-8")

if "async def send_emotion" not in s:
    s = s.rstrip() + '''


async def send_emotion(conn, emotion: str):
    """切换设备表情（thinking / happy / neutral ...）。"""
    try:
        payload = {"type": "llm", "emotion": emotion}
        await conn.websocket.send(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass
'''
    S.write_text(s, encoding="utf-8")
    ast.parse(s)
    print("sendAudioHandle：已加 send_emotion")

# ---------- 2) 工具调用前 → 思考表情 ----------
M = VS / "core" / "providers" / "tools" / "device_mcp" / "mcp_executor.py"
m = M.read_text(encoding="utf-8")

if "send_emotion" not in m:
    idx = None
    lines = m.split("\n")
    for i, ln in enumerate(lines):
        if "args_str = json.dumps" in ln:
            idx = i
            break
    if idx is None:
        print("⚠ 未找到 mcp_executor 插入点")
    else:
        indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
        block = [
            indent + "# 调用工具期间显示思考表情",
            indent + "try:",
            indent + "    from core.handle.sendAudioHandle import send_emotion",
            indent + '    await send_emotion(conn, "thinking")',
            indent + "except Exception:",
            indent + "    pass",
        ]
        lines[idx:idx] = block
        m = "\n".join(lines)
        M.write_text(m, encoding="utf-8")
        ast.parse(m)
        print("mcp_executor：工具调用前已切思考表情")

# ---------- 3) 开始说话 → 复原表情 ----------
if "restore_emotion" not in s:
    s = S.read_text(encoding="utf-8")
    old = '''    # 发送消息到客户端
    await conn.websocket.send(json.dumps(message))'''
    new = '''    # 开始出声前复原表情（思考 → 正常）
    if state == "start":
        try:
            await send_emotion(conn, "neutral")
        except Exception:
            pass

    # 发送消息到客户端
    await conn.websocket.send(json.dumps(message))'''
    if old in s:
        s = s.replace(old, new, 1)
        S.write_text(s, encoding="utf-8")
        ast.parse(s)
        print("sendAudioHandle：TTS 开始前复原表情")
    else:
        print("⚠ 未匹配 TTS 发送位置")
