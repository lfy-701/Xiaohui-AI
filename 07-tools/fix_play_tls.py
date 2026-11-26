"""修音乐推流：ffmpeg TLS 证书校验失败 → 先用 httpx 下载再本地解码。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

C = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
c = C.read_text(encoding="utf-8")

start = c.find("        async def _stream():")
end = c.find("        task = asyncio.create_task(_stream())")
if start < 0 or end < 0:
    print("⚠ 未找到 _stream")
    sys.exit(1)

new = '''        async def _stream():
            """先下载再本地解码：ffmpeg 自身 TLS 证书校验会失败。"""
            import os
            import tempfile

            sent = 0
            proc = None
            tmp = None
            try:
                import httpx as _httpx

                async with _httpx.AsyncClient(timeout=40.0, follow_redirects=True) as hc:
                    resp = await hc.get(url)
                    resp.raise_for_status()
                    data = resp.content

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                    fp.write(data)
                    tmp = fp.name
                conn.logger.bind(tag="Play").info(f"已下载 {len(data)} 字节，开始解码")

                proc = subprocess.Popen(
                    [ffmpeg, "-v", "error", "-nostdin", "-i", tmp,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ar", "24000", "-ac", "1", "pipe:1"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=0,
                )
                encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)
                frame = 1440
                stride = frame * 2

                conn.client_abort = False
                await sendAudioMessage(conn, SentenceType.FIRST, [], "")
                loop = asyncio.get_running_loop()
                while True:
                    if getattr(conn, "client_abort", False):
                        conn.logger.bind(tag="Play").info("播放被用户打断")
                        break
                    chunk = await loop.run_in_executor(None, proc.stdout.read, stride)
                    if not chunk:
                        break
                    chunk = chunk + b"\\x00" * (stride - len(chunk)) if len(chunk) < stride else chunk
                    try:
                        pkt = encoder.encode(chunk, frame)
                    except Exception:
                        continue
                    await sendAudioMessage(conn, SentenceType.MIDDLE, [pkt], None)
                    sent += 1
                    await asyncio.sleep(0.060)
                try:
                    await sendAudioMessage(conn, SentenceType.LAST, [], None)
                except Exception:
                    pass
            except Exception as e:
                conn.logger.bind(tag="Play").warning(f"流式播放失败: {e}")
            finally:
                try:
                    if proc and proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
                if sent == 0:
                    try:
                        err = (proc.stderr.read() or b"")[:300].decode("utf-8", "ignore")
                        conn.logger.bind(tag="Play").warning(f"仍无输出，stderr: {err}")
                    except Exception:
                        pass
                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")

'''

c = c[:start] + new + c[end:]
C.write_text(c, encoding="utf-8")
ast.parse(c)
print("已改为先下载再本地解码")
