"""播放音乐时：摇尾巴（摇晃）+ 循环切换彩色灯光（轻量，不抢连接）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "_music_vibe" in t:
    print("已存在")
    sys.exit(0)

helper = '''

async def _music_vibe(conn, stop_flag):
    """播放期间的伴舞：开场摇尾巴，之后每 8 秒只换一次灯（不占用对话通道）。"""
    import asyncio as _aio
    import json as _json

    colors = [
        (255, 60, 0), (255, 180, 0), (120, 255, 0),
        (0, 220, 120), (0, 180, 255), (120, 0, 255), (255, 0, 160),
    ]
    try:
        from core.providers.tools.device_mcp import call_mcp_tool
    except Exception:
        return

    async def _call(name, args, timeout=4):
        try:
            await _aio.wait_for(
                call_mcp_tool(conn, conn.mcp_client, name,
                              _json.dumps(args, ensure_ascii=False), timeout=timeout),
                timeout=timeout,
            )
        except Exception:
            pass

    # 开场：摇尾巴一下（摇晃感）
    await _call("self.dog_action", {"action": "wag"}, timeout=5)

    i = 0
    while not stop_flag.is_set():
        r, g, b = colors[i % len(colors)]
        i += 1
        await _call("self.set_led", {"r": r, "g": g, "b": b}, timeout=3)
        for _ in range(80):          # 8 秒一轮，随时可停
            if stop_flag.is_set():
                break
            await _aio.sleep(0.1)


'''

idx = t.find("    async def handle_play(self, request):")
if idx < 0:
    print("⚠ 未找到 handle_play")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在第一帧推送之后启动，避免抢握手
old = '''                await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")'''
new = '''                await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")
                _vibe_stop = asyncio.Event()
                _vibe_task = asyncio.create_task(_music_vibe(conn, _vibe_stop))'''

if old in t:
    t = t.replace(old, new, 1)
    print("已插入伴舞启动点")
else:
    print("⚠ 未匹配启动点")

# 结束停止
old2 = '''                try:
                    await sendAudioMessage(conn, SentenceType.LAST, [], None)
                    await _tts_msg(conn, "stop")
                except Exception:
                    pass'''
new2 = '''                try:
                    _vibe_stop.set()
                except Exception:
                    pass
                try:
                    await sendAudioMessage(conn, SentenceType.LAST, [], None)
                    await _tts_msg(conn, "stop")
                except Exception:
                    pass'''

if old2 in t:
    t = t.replace(old2, new2, 1)
    print("已加停止标志")
else:
    print("⚠ 未匹配结束点")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
