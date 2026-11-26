"""点歌前加一句即时回应（缓存音频，播放约 0.6 秒）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

R = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = R.read_text(encoding="utf-8")

if "_speak_ack" in t:
    print("已存在")
    sys.exit(0)

helper = '''

_ACK_CACHE = {}


async def _speak_ack(conn, text: str = "好，这就放给你听。"):
    """用 EdgeTTS 合成一句短回应并播放，音频缓存复用。"""
    try:
        import edge_tts

        from core.handle.sendAudioHandle import sendAudioMessage
        from core.providers.tts.dto.dto import SentenceType
        from core.utils.util import audio_to_data

        voice = "zh-CN-XiaoxiaoNeural"
        try:
            from core.utils.voice_settings import load as _load_rt
            voice = (_load_rt().get("voice") or voice)
        except Exception:
            pass

        key = text + voice
        path = _ACK_CACHE.get(key)
        if not path:
            import tempfile

            p = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            p.close()
            comm = edge_tts.Communicate(text, voice=voice)
            audio = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            with open(p.name, "wb") as f:
                f.write(audio)
            path = p.name
            _ACK_CACHE[key] = path

        packets, _ = audio_to_data(path)
        conn.client_abort = False
        await sendAudioMessage(conn, SentenceType.FIRST, packets, text)
        await sendAudioMessage(conn, SentenceType.LAST, [], None)
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"回应播报失败: {e}")


'''

idx = t.find("async def _try_play_music")
if idx < 0:
    print("⚠ 未找到 _try_play_music")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在调用播放接口之前说那句回应
old = '''        base = "http://127.0.0.1:8080"
        async with httpx.AsyncClient(timeout=120.0) as c:'''
new = '''        # 先说一句，掩盖搜索/缓冲的等待
        await _speak_ack(conn)

        base = "http://127.0.0.1:8080"
        async with httpx.AsyncClient(timeout=120.0) as c:'''

if old in t:
    t = t.replace(old, new, 1)
    R.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已加即时回应")
else:
    print("⚠ 未找到播放调用点")
