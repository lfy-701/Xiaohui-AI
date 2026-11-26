"""唱歌时切换表情：播放期间每隔 10 秒换一个表情，最多 3 次（轻量，避免占连接）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "_music_faces" in t:
    print("已存在")
    sys.exit(0)

helper = '''

async def _music_faces(conn, stop_flag):
    """播放音乐期间换表情：只发 3 次，间隔 10 秒，避免拖累连接。"""
    import asyncio as _aio
    import json as _json

    seq = ["happy", "love", "wink"]
    try:
        from core.providers.tools.device_mcp import call_mcp_tool
    except Exception:
        return

    for expr in seq:
        for _ in range(100):        # 10 秒等待，期间可被停止
            if stop_flag.is_set():
                return
            await _aio.sleep(0.1)
        if stop_flag.is_set():
            return
        try:
            await _aio.wait_for(
                call_mcp_tool(conn, conn.mcp_client, "self.face_expression",
                              _json.dumps({"expression": expr}, ensure_ascii=False),
                              timeout=3),
                timeout=3,
            )
            conn.logger.bind(tag="Play").info(f"唱歌表情：{expr}")
        except Exception:
            pass


'''

idx = t.find("    async def handle_play(self, request):")
if idx < 0:
    print("⚠ 未找到 handle_play")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 起始表情 + 启动任务（放在第一帧之后）
old = '''                await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")'''
new = '''                await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")
                _face_stop = asyncio.Event()
                asyncio.create_task(_music_faces(conn, _face_stop))'''

if old in t:
    t = t.replace(old, new, 1)
    print("已插入表情任务")
else:
    print("⚠ 未匹配启动点")

old2 = '''                await sendAudioMessage(conn, SentenceType.LAST, [], None)
                await _tts_msg(conn, "stop")'''
new2 = '''                try:
                    _face_stop.set()
                except Exception:
                    pass
                await sendAudioMessage(conn, SentenceType.LAST, [], None)
                await _tts_msg(conn, "stop")'''

if old2 in t:
    t = t.replace(old2, new2, 1)
    print("已加停止标志")
else:
    print("⚠ 未匹配结束点")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
