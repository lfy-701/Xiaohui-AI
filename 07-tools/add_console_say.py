"""给语音服务加 /api/console/say：控制台打字 → 设备说出来。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "handle_say" in t:
    print("已存在")
    sys.exit(0)

anchor = "    async def handle_action(self, request):"
say = '''    async def handle_say(self, request):
        """POST /api/console/say  {"text": "我在，你说。"}

        让当前在线的设备把这段文字说出来（TTS + 已有的音频通道）。
        """
        import io

        try:
            body = await request.json()
        except Exception:
            return self._respond({"ok": False, "error": "请求体不是合法 JSON"}, 400)

        text = str((body or {}).get("text") or "").strip()
        if not text:
            return self._respond({"ok": False, "error": "缺少 text"}, 400)
        if len(text) > 300:
            text = text[:300]

        device_id = str((body or {}).get("device_id") or "").strip()
        conn = await self._pick_connection(device_id)
        if conn is None:
            return self._respond(
                {"ok": False, "error": "设备当前不在线（需要先语音唤醒）"}, 409
            )

        tts = getattr(conn, "tts", None)
        if tts is None:
            return self._respond({"ok": False, "error": "语音合成未就绪"}, 503)

        try:
            audio = await tts.text_to_speak(text, None)
        except Exception as e:
            return self._respond({"ok": False, "error": f"合成失败：{e}"}, 500)
        if not audio:
            return self._respond({"ok": False, "error": "合成结果为空"}, 500)

        try:
            from core.utils.util import audio_bytes_to_data
            opus_packets = audio_bytes_to_data(audio)
        except Exception:
            try:
                from core.utils.util import audio_to_data
                import tempfile, os
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                    fp.write(audio)
                    tmp_path = fp.name
                opus_packets, _ = audio_to_data(tmp_path)
                os.unlink(tmp_path)
            except Exception as e:
                return self._respond({"ok": False, "error": f"编码失败：{e}"}, 500)

        try:
            from core.handle.sendAudioHandle import sendAudioMessage
            from core.providers.tts.dto.dto import SentenceType

            conn.client_abort = False
            await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, text)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)
        except Exception as e:
            return self._respond({"ok": False, "error": f"发送失败：{e}"}, 500)

        return self._respond({"ok": True, "said": text, "packets": len(opus_packets)})

'''

if anchor in t:
    t = t.replace(anchor, say + anchor, 1)
    F.write_text(t, encoding="utf-8")
    print("已加 handle_say")
else:
    print("⚠ 锚点不匹配")
    sys.exit(1)

import ast
ast.parse(t)
print("语法 OK")
