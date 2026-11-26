"""控制台：新增 /api/console/speak（先确保设备连上再推音频）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "console/speak" in t:
    print("已存在")
    sys.exit(0)

code = '''

@app.post("/api/console/speak")
def api_console_speak(body: Dict[str, Any]):
    """网页播报：先确保设备连上（空闲约 4 秒会断开），连上后立刻推音频。"""
    import time as _t

    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "缺少 text")
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    def _try_say():
        try:
            with httpx.Client(timeout=60.0) as c:
                r = c.post(f"{VOICE_HTTP_BASE}/api/console/say", json={"text": text})
                return r.status_code, r.json()
        except Exception as e:
            return 502, {"ok": False, "error": str(e)}

    code, data = _try_say()
    if code == 200 and data.get("ok"):
        return data

    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: d.get("last_seen") or 0, reverse=True)
    if devs:
        try:
            store.push_command(devs[0]["mac"], "connect", "1")
        except Exception:
            pass

    deadline = _t.time() + 12
    while _t.time() < deadline:
        _t.sleep(0.8)
        code, data = _try_say()
        if code == 200 and data.get("ok"):
            return data

    return {"ok": False, "error": data.get("error") or "设备未响应"}
'''

t = t.rstrip() + code
M.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加 /api/console/speak")
