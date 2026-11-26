"""修复 say 接口音频：24kHz 编码 + 逐包间隔发送。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

start = t.find("        # MP3 -> 16k 单声道 PCM")
end = t.find("        return self._respond({\"ok\": True, \"said\": text")
if start < 0 or end < 0:
    print("⚠ 找不到音频块")
    sys.exit(1)

block = '''        # MP3 -> 24k 单声道 PCM -> 24k Opus（设备播放通道是 24kHz）
        try:
            import asyncio as _asyncio
            import os as _os
            import subprocess
            import tempfile

            import numpy as _np
            import opuslib_next as _opus

            ffmpeg = None
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg = "ffmpeg"

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                fp.write(audio)
                tmp_path = fp.name

            try:
                proc = subprocess.run(
                    [ffmpeg, "-v", "quiet", "-nostdin", "-i", tmp_path,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ar", "24000", "-ac", "1", "-"],
                    capture_output=True, timeout=30,
                )
                if proc.returncode != 0 or not proc.stdout:
                    raise RuntimeError((proc.stderr or b"")[:200].decode("utf-8", "ignore"))
                pcm = proc.stdout
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass

            encoder = _opus.Encoder(24000, 1, _opus.APPLICATION_AUDIO)
            frame = 1440  # 24000Hz * 60ms
            stride = frame * 2
            opus_packets = []
            for i in range(0, len(pcm), stride):
                chunk = pcm[i:i + stride]
                if len(chunk) < stride:
                    chunk = chunk + b"\\x00" * (stride - len(chunk))
                _np.frombuffer(chunk, dtype=_np.int16)  # 校验可解析
                opus_packets.append(encoder.encode(chunk, frame))
        except Exception as e:
            return self._respond({"ok": False, "error": f"编码失败：{e}"}, 500)

        # 逐包发送，每帧间隔 60ms，模拟实时播放，避免设备缓冲溢出
        try:
            from core.handle.sendAudioHandle import sendAudioMessage
            from core.providers.tts.dto.dto import SentenceType

            conn.client_abort = False
            await sendAudioMessage(conn, SentenceType.FIRST, [], text)
            for pkt in opus_packets:
                await sendAudioMessage(conn, SentenceType.MIDDLE, [pkt], None)
                await _asyncio.sleep(0.06)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)
        except Exception as e:
            return self._respond({"ok": False, "error": f"发送失败：{e}"}, 500)

'''

t = t[:start] + block + t[end:]
F.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("已改写音频编码与发送，语法 OK")
