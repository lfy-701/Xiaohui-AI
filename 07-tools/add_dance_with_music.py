"""唱歌时跳舞：播放音乐期间周期性下发动作/灯效。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "_dance_while_playing" in t:
    print("已存在")
    sys.exit(0)

helper = '''

async def _dance_while_playing(conn, stop_flag):
    """播放音乐期间循环做动作 + 换灯，制造「边唱边跳」。"""
    import asyncio as _aio
    import json as _json

    seq = [
        ("self.dog_action", {"action": "dance"}),
        ("self.set_led", {"r": 255, "g": 80, "b": 0}),
        ("self.dog_action", {"action": "wag"}),
        ("self.set_led", {"r": 0, "g": 200, "b": 255}),
        ("self.dog_action", {"action": "shake"}),
        ("self.set_led", {"r": 180, "g": 0, "b": 255}),
    ]
    i = 0
    try:
        from core.providers.tools.device_mcp import call_mcp_tool

        while not stop_flag.is_set():
            name, args = seq[i % len(seq)]
            i += 1
            try:
                await call_mcp_tool(conn, conn.mcp_client, name,
                                    _json.dumps(args, ensure_ascii=False), timeout=6)
            except Exception:
                pass
            for _ in range(60):          # 每 6 秒一轮，期间响应停止
                if stop_flag.is_set():
                    break
                await _aio.sleep(0.1)
    except Exception:
        pass


'''

idx = t.find("    async def handle_play(self, request):")
if idx < 0:
    print("⚠ 未找到 handle_play")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在 _stream 的发送前启动，结束后停止
old = '''                conn.client_abort = False
                from core.handle.sendAudioHandle import send_tts_message as _tts_msg'''
new = '''                conn.client_abort = False
                from core.handle.sendAudioHandle import send_tts_message as _tts_msg
                # 边唱边跳
                _dance_stop = asyncio.Event()
                asyncio.create_task(_dance_while_playing(conn, _dance_stop))'''

if old in t:
    t = t.replace(old, new, 1)
    print("已启动跳舞任务")
else:
    print("⚠ 未匹配启动点")

# 结束时置停止标志
old2 = '''                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")'''
new2 = '''                try:
                    _dance_stop.set()
                except Exception:
                    pass
                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")'''
if old2 in t:
    t = t.replace(old2, new2, 1)
    print("已加停止标志")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
