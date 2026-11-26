"""音乐播放：先整首解码到内存，再匀速推帧（消除 ffmpeg 管道抖动）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

start = t.find("        async def _stream():")
end = t.find("        task = asyncio.create_task(_stream())")
if start < 0 or end < 0:
    print("⚠ 未找到 _stream")
    sys.exit(1)

new = '''        async def _stream():
            """下载 → 整首解码到内存 → 匀速推帧。"""
            import os
            import tempfile

            sent = 0
            tmp = None
            try:
                import httpx as _httpx

                async with _httpx.AsyncClient(timeout=60.0, follow_redirects=True) as hc:
                    resp = await hc.get(url)
                    resp.raise_for_status()
                    data = resp.content

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                    fp.write(data)
                    tmp = fp.name

                # 一次性解码成完整 PCM（30 秒约 1.4 MB，内存无压力）
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
                    conn.logger.bind(tag="Play").warning(
                        "解码无输出: " + (proc.stderr or b"")[:200].decode("utf-8", "ignore"))
                    return
                conn.logger.bind(tag="Play").info(f"已解码 {len(pcm)} 字节 PCM")

                encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)
                frame = 1440
                stride = frame * 2
                packets = []
                for i in range(0, len(pcm), stride):
                    chunk = pcm[i:i + stride]
                    if len(chunk) < stride:
                        chunk = chunk + b"\\x00" * (stride - len(chunk))
                    packets.append(encoder.encode(chunk, frame))

                conn.client_abort = False
                await _tts_msg(conn, "start")
                await sendAudioMessage(conn, SentenceType.FIRST, [packets[0]], "")
                # 每 120ms 推 2 帧，节奏稳定，设备缓冲不容易断
                i = 1
                while i < len(packets):
                    if getattr(conn, "client_abort", False):
                        conn.logger.bind(tag="Play").info("播放被用户打断")
                        break
                    batch = packets[i:i + 2]
                    await sendAudioMessage(conn, SentenceType.MIDDLE, batch, None)
                    sent += len(batch)
                    i += 2
                    await asyncio.sleep(0.120)
                try:
                    await sendAudioMessage(conn, SentenceType.LAST, [], None)
                    await _tts_msg(conn, "stop")
                except Exception:
                    pass
            except Exception as e:
                conn.logger.bind(tag="Play").warning(f"流式播放失败: {e}")
            finally:
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
                conn.logger.bind(tag="Play").info(f"播放结束：{sent} 帧 / {sent * 0.06:.1f} 秒")

'''

t = t[:start] + new + t[end:]
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已改为整首解码 + 匀速推帧")
