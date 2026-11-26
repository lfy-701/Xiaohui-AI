"""彻底消除叠音：打断时真正停掉上一段 TTS/LLM 流，而不是只发 stop。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = P.read_text(encoding="utf-8")

old = '''async def _interrupt_speaking(conn):
    """停掉所有正在播的语音（含 LLM/TTS 队列），避免叠音。"""
    try:
        from core.handle.sendAudioHandle import send_tts_message

        conn.client_abort = False        # 不置打断位，避免 TTS 线程被终止后发不出 stop
        try:
            conn.clear_queues()
        except Exception:
            pass
        await send_tts_message(conn, "stop")
        conn.client_is_speaking = False
        try:
            conn.clearSpeakStatus()
        except Exception:
            pass
    except Exception:
        pass'''

new = '''async def _interrupt_speaking(conn):
    """彻底停掉上一段语音（LLM/TTS 队列 + 播放线程），杜绝两段音频叠加。"""
    try:
        from core.handle.sendAudioHandle import send_tts_message

        # 1) 打断位：让正在跑的 LLM/TTS 循环立刻退出
        conn.client_abort = True
        try:
            conn.clear_queues()
        except Exception:
            pass

        # 2) 停播放线程（真正掐断正在输出的音频）
        try:
            conn.tts.stop()
        except Exception:
            pass

        # 3) 通知设备停止播放
        await send_tts_message(conn, "stop")
        conn.client_is_speaking = False
        try:
            conn.clearSpeakStatus()
        except Exception:
            pass

        # 4) 等上一段彻底收尾，再开口
        await asyncio.sleep(0.25)
        conn.client_abort = False
    except Exception:
        pass'''

if old in t:
    t = t.replace(old, new, 1)
    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("打断逻辑：已改为彻底停止（abort + tts.stop + stop + 等待）")
else:
    print("⚠ 未匹配")
