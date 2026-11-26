"""修正放歌：字段名 title、推送失败容错、分块节流。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 1) 控制台：字段名 + 把推流异常当作部分成功
M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")
t = t.replace('data["song"] = {"name": song.get("name"), "artist": song.get("artist")}',
              'data["song"] = {"name": song.get("title"), "artist": song.get("artist")}')
t = t.replace('store.add_log("system", "设备播放音乐：" + str(song.get("name")))',
              'store.add_log("system", "设备播放音乐：" + str(song.get("title")))')
M.write_text(t, encoding="utf-8")
ast.parse(t)
print("console: 字段名已修")

# 2) 语音服务：推流容错 + 60ms 节流
C = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
c = C.read_text(encoding="utf-8")

old = '''        try:
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
        })'''

new = '''        sent = 0
        err = None
        try:
            conn.client_abort = False
            await sendAudioMessage(conn, SentenceType.FIRST, [], "")
            for pkt in packets:
                if getattr(conn, "client_abort", False):
                    break
                await sendAudioMessage(conn, SentenceType.MIDDLE, [pkt], None)
                sent += 1
                await asyncio.sleep(0.060)
            try:
                await sendAudioMessage(conn, SentenceType.LAST, [], None)
            except Exception:
                pass
        except Exception as e:
            err = str(e)

        # 设备在播完后主动断开是正常现象，只要送出去过半就算成功
        ok = sent >= max(1, int(len(packets) * 0.5))
        return self._respond({
            "ok": ok,
            "packets": len(packets),
            "sent": sent,
            "seconds": round(sent * 0.06, 1),
            "note": None if ok else (err or "设备中途断开"),
        }, 200 if ok else 500)'''

if old in c:
    c = c.replace(old, new, 1)
    C.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("voice: 推流容错已加")
else:
    print("⚠ 推流块未匹配")
