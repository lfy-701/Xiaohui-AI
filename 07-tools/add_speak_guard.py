"""加看门狗：长时间「标记在说话但没收到语音」时强制复位，避免卡死。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = P.read_text(encoding="utf-8")

if "_speak_stuck_guard" not in t:
    HELPER = '''

_speak_guard_task = {}


async def _speak_stuck_guard(conn):
    """每 5 秒检查：若长时间标记在说话且没有新语音，强制回到可收音状态。"""
    last_seen = getattr(conn, "client_have_voice", False)
    idle = 0
    while True:
        await asyncio.sleep(5)
        try:
            speaking = bool(getattr(conn, "client_is_speaking", False))
            have_voice = bool(getattr(conn, "client_have_voice", False))
            if have_voice != last_seen:
                last_seen = have_voice
                idle = 0
                continue
            idle += 5
            # 说话状态但 25 秒没有任何新语音 → 大概率卡死
            if speaking and idle >= 25:
                from core.handle.sendAudioHandle import send_tts_message

                conn.logger.bind(tag=TAG).warning("检测到说话状态卡死，强制复位")
                conn.client_is_speaking = False
                conn.client_abort = False
                conn.just_woken_up = False
                try:
                    conn.clearSpeakStatus()
                except Exception:
                    pass
                try:
                    conn.asr_audio.clear()
                except Exception:
                    pass
                await send_tts_message(conn, "stop")
                idle = 0
        except asyncio.CancelledError:
            return
        except Exception:
            pass


def _ensure_speak_guard(conn):
    task = _speak_guard_task.get(id(conn))
    if task is None or task.done():
        import asyncio as _aio

        _speak_guard_task[id(conn)] = _aio.create_task(_speak_stuck_guard(conn))
'''

    idx = t.find("async def handleAudioMessage")
    if idx > 0:
        t = t[:idx] + HELPER.strip() + "\n\n\n" + t[idx:]

    # 在收音频入口启动看门狗
    old = '''async def handleAudioMessage(conn, audio):
    # 当前片段是否有人说话
    have_voice = conn.vad.is_vad(conn, audio)'''
    new = '''async def handleAudioMessage(conn, audio):
    try:
        _ensure_speak_guard(conn)
    except Exception:
        pass
    # 当前片段是否有人说话
    have_voice = conn.vad.is_vad(conn, audio)'''
    if old in t:
        t = t.replace(old, new, 1)
        print("看门狗：已挂到 handleAudioMessage")

    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("语法 OK")
else:
    print("已存在")
