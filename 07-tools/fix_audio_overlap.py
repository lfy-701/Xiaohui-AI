"""修复语音重叠：所有自发播报串行化，并在开口前先打断正在播放的语音。

思路：
1) 每个连接一把音频锁（conn._audio_lock），_speak_ack 全程持有
2) 开口前先发 abort/tts stop，让设备停下当前正在播的内容
3) 音乐播放也拿同一把锁，避免和回应叠在一起
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
F = VS / "core" / "handle" / "receiveAudioHandle.py"
t = F.read_text(encoding="utf-8")

if "_audio_lock" in t:
    print("已存在音频锁")
    sys.exit(0)

# ---------- 1) 工具函数：拿锁 + 打断 ----------
HELPER = '''async def _audio_lock_for(conn):
    """每连接一把音频锁，保证同一时刻只有一段语音在播。"""
    import asyncio as _aio

    lock = getattr(conn, "_audio_lock", None)
    if lock is None:
        lock = _aio.Lock()
        try:
            conn._audio_lock = lock
        except Exception:
            pass
    return lock


async def _interrupt_speaking(conn):
    """让设备停下当前正在播的语音，避免新语音叠上去。"""
    try:
        from core.handle.sendAudioHandle import send_tts_message

        conn.client_abort = True
        await send_tts_message(conn, "stop")
        await asyncio.sleep(0.12)
        conn.client_abort = False
        conn.client_is_speaking = False
        try:
            conn.clearSpeakStatus()
        except Exception:
            pass
    except Exception:
        pass


'''

idx = t.find("async def _speak_ack")
if idx < 0:
    print("⚠ 未找到 _speak_ack")
    sys.exit(1)
t = t[:idx] + HELPER + t[idx:]

# ---------- 2) _speak_ack 加锁 + 先打断 ----------
old_head = '''async def _speak_ack(conn, text: str = "好，这就放给你听。"):
    """用 EdgeTTS 合成一句短回应并播放，音频缓存复用。"""
    try:'''
new_head = '''async def _speak_ack(conn, text: str = "好，这就放给你听。"):
    """用 EdgeTTS 合成一句短回应并播放；串行执行，避免与其它语音重叠。"""
    lock = await _audio_lock_for(conn)
    async with lock:
        await _speak_ack_locked(conn, text)


async def _speak_ack_locked(conn, text: str = "好，这就放给你听。"):
    try:'''
if old_head in t:
    t = t.replace(old_head, new_head, 1)
    print("_speak_ack：已加锁")

# 播放前先打断
old_start = '''        # 先发 tts start，设备才会进入播放状态
        from core.handle.sendAudioHandle import send_tts_message

        await send_tts_message(conn, "start")'''
new_start = '''        # 先打断正在播的内容，再进入本段播放
        await _interrupt_speaking(conn)

        from core.handle.sendAudioHandle import send_tts_message

        await send_tts_message(conn, "start")'''
if old_start in t:
    t = t.replace(old_start, new_start, 1)
    print("_speak_ack：开口前已先打断")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("receiveAudioHandle：语法 OK")

# ---------- 3) 音乐播放也用同一把锁 ----------
C = VS / "core" / "api" / "console_handler.py"
c = C.read_text(encoding="utf-8")
if "_audio_lock_for" not in c:
    old = '''        async def _stream():
            sent = 0
            tmp = None
            try:'''
    new = '''        async def _stream():
            from core.handle.receiveAudioHandle import _audio_lock_for, _interrupt_speaking

            lock = await _audio_lock_for(conn)
            async with lock:
                await _interrupt_speaking(conn)
                await _stream_locked()

        async def _stream_locked():
            sent = 0
            tmp = None
            try:'''
    if old in c:
        c = c.replace(old, new, 1)
        C.write_text(c, encoding="utf-8")
        ast.parse(c)
        print("音乐播放：已加同一把锁")
    else:
        print("⚠ 音乐播放未匹配")
