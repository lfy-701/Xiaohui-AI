"""重写 handle_say：edge-tts 合成 → ffmpeg 转 PCM → Opus 推流。
不依赖 pydub/ffprobe，Windows 上最稳。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
lines = F.read_text(encoding="utf-8").split("\n")

# 找到 handle_say 的整个函数体（从 def 到下一个 async def）
start = end = None
for i, ln in enumerate(lines):
    if start is None and ln.strip().startswith("async def handle_say"):
        start = i
    elif start is not None and ln.strip().startswith("async def handle_play"):
        end = i
        break

if start is None or end is None:
    print("⚠ 未定位 handle_say")
    sys.exit(1)

IND = " " * 8
BODY = " " * 12

new = f'''    async def handle_say(self, request):
        """把文字合成成语音推给设备（edge-tts → ffmpeg PCM → Opus）。"""
        import os as _os
        import tempfile as _tf

        import edge_tts
        import imageio_ffmpeg
        import opuslib_next as opus
        import subprocess as _sp

        try:
            body = await request.json()
        except Exception:
            return self._respond({{"ok": False, "error": "请求体不是合法 JSON"}}, 400)

        text = str((body or {{}}).get("text") or "").strip()
        if not text:
            return self._respond({{"ok": False, "error": "缺少 text"}}, 400)

        conn = await self._pick_connection(str((body or {{}}).get("device_id") or ""))
        if conn is None:
            return self._respond({{"ok": False, "error": "设备当前不在线"}}, 409)

        from core.handle.sendAudioHandle import sendAudioMessage, send_tts_message
        from core.providers.tts.dto.dto import SentenceType

        voice = ""
        for attr in ("voice", "voice_name"):
            voice = voice or str(getattr(conn, attr, "") or "")
        tts_obj = getattr(conn, "tts", None)
        if not voice and tts_obj is not None:
            voice = str(getattr(tts_obj, "voice", "") or "")
        voice = voice or "zh-CN-XiaoxiaoNeural"

        mp3 = wav = None
        try:
            f1 = _tf.NamedTemporaryFile(suffix=".mp3", delete=False)
            f1.close()
            mp3 = f1.name
            await edge_tts.Communicate(text, voice).save(mp3)

            wav = mp3 + ".wav"
            _sp.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", mp3,
                 "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", wav],
                check=True, timeout=90,
            )
            pcm = open(wav, "rb").read()
            if not pcm:
                return self._respond({{"ok": False, "error": "合成结果为空"}}, 500)

            encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)
            encoder.bitrate = 24000
            frame = 1440
            stride = frame * 2
            packets = []
            for i in range(0, len(pcm), stride):
                chunk = pcm[i:i + stride]
                if len(chunk) < stride:
                    chunk = chunk + b"\\x00" * (stride - len(chunk))
                packets.append(encoder.encode(chunk, frame))

            conn.client_abort = False
            await send_tts_message(conn, "start")
            await sendAudioMessage(conn, SentenceType.FIRST, packets[:2], text)
            for i in range(2, len(packets)):
                await sendAudioMessage(conn, SentenceType.MIDDLE, [packets[i]], None)
                await asyncio.sleep(0.055)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)
            await send_tts_message(conn, "stop")
            return self._respond({{"ok": True, "spoken": True, "packets": len(packets), "voice": voice}})
        except Exception as e:
            return self._respond({{"ok": False, "error": f"播报失败: {{e}}"}}, 500)
        finally:
            for p in (mp3, wav):
                try:
                    if p and _os.path.exists(p):
                        _os.unlink(p)
                except Exception:
                    pass

'''

lines[start:end] = new.split("\n")
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("handle_say 已重写（edge-tts 直连）；语法 OK")
