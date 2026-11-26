"""语音服务：新增 /api/console/play，把网络音频流推到设备播放。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "handle_play" in t:
    print("已存在")
    sys.exit(0)

anchor = "    async def handle_action(self, request):"
code = '''    async def handle_play(self, request):
        """POST /api/console/play  {"url": "https://...mp3", "loops": 1}

        把网络音频下载后转成 24kHz Opus，按 60ms 一帧推给设备播放。
        """
        import asyncio
        import os
        import subprocess
        import tempfile

        import httpx
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
            return self._respond({"ok": False, "error": "设备当前不在线（需要先语音唤醒）"}, 409)

        ffmpeg = None
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = "ffmpeg"

        # 下载
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as c:
                r = c.get(url)
                r.raise_for_status()
                raw = r.content
        except Exception as e:
            return self._respond({"ok": False, "error": f"下载失败：{e}"}, 500)

        tmp_in = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                fp.write(raw)
                tmp_in = fp.name
            proc = subprocess.run(
                [ffmpeg, "-v", "quiet", "-nostdin", "-i", tmp_in,
                 "-f", "s16le", "-acodec", "pcm_s16le",
                 "-ar", "24000", "-ac", "1", "-"],
                capture_output=True, timeout=60,
            )
            if proc.returncode != 0 or not proc.stdout:
                raise RuntimeError((proc.stderr or b"")[:200].decode("utf-8", "ignore"))
            pcm = proc.stdout
        except Exception as e:
            return self._respond({"ok": False, "error": f"转码失败：{e}"}, 500)
        finally:
            try:
                if tmp_in:
                    os.unlink(tmp_in)
            except Exception:
                pass

        # 编码 60ms 帧
        encoder = opus.Encoder(24000, 1, opus.APPLICATION_AUDIO)
        stride = 1440 * 2
        packets = []
        for i in range(0, len(pcm), stride):
            chunk = pcm[i:i + stride]
            if len(chunk) < stride:
                chunk = chunk + b"\\x00" * (stride - len(chunk))
            packets.append(encoder.encode(chunk, 1440))

        if not packets:
            return self._respond({"ok": False, "error": "音频为空"}, 500)

        # 推流：每帧间隔 58ms（略快于实时，避免缓冲堆积）
        from core.handle.sendAudioHandle import sendAudioMessage
        from core.providers.tts.dto.dto import SentenceType

        try:
            conn.client_abort = False
            await sendAudioMessage(conn, SentenceType.FIRST, [], "")
            for pkt in packets:
                if getattr(conn, "client_abort", False):
                    break
                await sendAudioMessage(conn, SentenceType.MIDDLE, [pkt], None)
                await asyncio.sleep(0.058)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)
        except Exception as e:
            return self._respond({"ok": False, "error": f"推流失败：{e}"}, 500)

        return self._respond({
            "ok": True, "packets": len(packets),
            "seconds": round(len(packets) * 0.06, 1),
        })

'''

if anchor in t:
    t = t.replace(anchor, code + anchor, 1)
    F.write_text(t, encoding="utf-8")
    print("已加 handle_play")
else:
    print("⚠ 锚点不匹配")
    sys.exit(1)

# 注册路由
HF = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\http_server.py")
h = HF.read_text(encoding="utf-8")
if "/api/console/play" not in h:
    old = '            web.options("/api/console/say", self.console_handler.handle_options),'
    new = old + '''
            web.post("/api/console/play", self.console_handler.handle_play),
            web.options("/api/console/play", self.console_handler.handle_options),'''
    if old in h:
        h = h.replace(old, new, 1)
        HF.write_text(h, encoding="utf-8")
        print("已注册 /api/console/play")

ast.parse(F.read_text(encoding="utf-8"))
print("语法 OK")
