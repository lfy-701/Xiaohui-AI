"""重建 handle_play（音乐播放接口）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "async def handle_play" in t:
    print("已存在")
    sys.exit(0)

code = '''    async def handle_play(self, request):
        """POST /api/console/play  {"url": "..."}  播放网络音频（音乐）。"""
        import os
        import subprocess
        import tempfile

        import opuslib_next as opus

        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        url = str((body or {}).get("url") or "").strip()
        if not url.startswith("http"):
            return self._respond({"ok": False, "error": "缺少合法的 url"}, 400)

        conn = await self._pick_connection(str((body or {}).get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)

        ffmpeg = "ffmpeg"
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        from core.handle.sendAudioHandle import sendAudioMessage, send_tts_message
        from core.providers.tts.dto.dto import SentenceType

        async def _stream():
            sent = 0
            tmp = None
            try:
                import asyncio as _aio
                import httpx as _httpx

                async with _httpx.AsyncClient(timeout=60.0, follow_redirects=True) as hc:
                    resp = await hc.get(url)
                    resp.raise_for_status()
                    data = resp.content

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                    fp.write(data)
                    tmp = fp.name

                loop = asyncio.get_running_loop()
                proc = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        [ffmpeg, "-v", "error", "-nostdin", "-i", tmp,
                         "-f", "s16le", "-acodec", "pcm_s16le",
                         "-ar", "24000", "-ac", "1", "pipe:1"],
                        capture_output=True, timeout=90,
                    ),
                )
                pcm = proc.stdout or b""
                if not pcm:
                    conn.logger.bind(tag="Play").warning("解码无输出")
                    return
                conn.logger.bind(tag="Play").info(f"已解码 {len(pcm)} 字节 PCM")

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
                await sendAudioMessage(conn, SentenceType.FIRST, packets[:3], "")
                await asyncio.sleep(0.05)

                i = 3
                while i < len(packets):
                    if getattr(conn, "client_abort", False):
                        conn.logger.bind(tag="Play").info("播放被用户打断")
                        break
                    await sendAudioMessage(conn, SentenceType.MIDDLE, packets[i:i + 1], None)
                    i += 1
                    await asyncio.sleep(0.055)
                sent = i

                try:
                    await sendAudioMessage(conn, SentenceType.LAST, [], None)
                    await send_tts_message(conn, "stop")
                except Exception:
                    pass
            except Exception as e:
                conn.logger.bind(tag="Play").warning(f"播放失败: {e}")
            finally:
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")

        asyncio.create_task(_stream())
        return self._respond({"ok": True, "async": True, "stream": True})

'''

idx = t.find("    async def handle_stop(self, request):")
if idx < 0:
    print("⚠ 未找到插入点")
    sys.exit(1)
t = t[:idx] + code + t[idx:]
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已重建 handle_play")
