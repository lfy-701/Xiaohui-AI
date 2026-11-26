"""修复网页播报：发送 tts start/stop，让设备进入播放状态。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "send_tts_message(conn, \"start\")" in t:
    print("已存在")
    sys.exit(0)

old = '''            conn.client_abort = False
            await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, text)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)'''

new = '''            from core.handle.sendAudioHandle import send_tts_message

            conn.client_abort = False
            # 关键：先发 tts start，设备才会切到「说话」状态，否则音频被丢弃
            await send_tts_message(conn, "start")
            await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, text)
            await sendAudioMessage(conn, SentenceType.LAST, [], None)
            await send_tts_message(conn, "stop")'''

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已加 tts start/stop")
else:
    print("⚠ 未匹配发送块")
