"""音乐：搜索列表 + 暂停播放。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")

# ---------- 1) 语音服务：停止接口 ----------
C = VS / "core" / "api" / "console_handler.py"
c = C.read_text(encoding="utf-8")
if "handle_stop" not in c:
    code = '''
    async def handle_stop(self, request):
        """POST /api/console/stop  停止当前播放（音乐/播报）。"""
        try:
            body = await request.json()
        except Exception:
            body = {}
        conn = await self._pick_connection(str((body or {}).get("device_id") or ""))
        if conn is None:
            return self._respond({"ok": False, "error": "设备当前不在线"}, 409)
        try:
            conn.client_abort = True
        except Exception:
            pass
        try:
            from core.handle.sendAudioHandle import send_tts_message
            await send_tts_message(conn, "stop")
        except Exception:
            pass
        return self._respond({"ok": True, "stopped": True})

'''
    idx = c.find("    async def handle_play(self, request):")
    c = c[:idx] + code + c[idx:]
    C.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("voice: 已加 handle_stop")

H = VS / "core" / "http_server.py"
h = H.read_text(encoding="utf-8")
if "/api/console/stop" not in h:
    old = '            web.post("/api/console/play", self.console_handler.handle_play),'
    new = ('            web.post("/api/console/stop", self.console_handler.handle_stop),'
           '\r\n            web.options("/api/console/stop", self.console_handler.handle_options),'
           '\r\n' + old)
    h = h.replace(old, new, 1)
    H.write_text(h, encoding="utf-8")
    print("voice: 已注册 /api/console/stop")

# ---------- 2) 控制台：停止代理 ----------
M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
m = M.read_text(encoding="utf-8")
if "/api/music/stop" not in m:
    code2 = '''

@app.post("/api/music/stop")
def api_music_stop():
    """停止设备当前播放。"""
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/stop", json={})
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
'''
    m = m.rstrip() + code2
    M.write_text(m, encoding="utf-8")
    ast.parse(m)
    print("console: 已加 /api/music/stop")
