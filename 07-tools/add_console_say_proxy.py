"""给控制台加 /api/console/say 代理。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "/api/console/say" in t:
    print("已存在")
    sys.exit(0)

route = '''

@app.post("/api/console/say")
async def api_console_say(request: Request):
    """让在线设备把这段文字说出来（需要设备处于语音会话中）。"""
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "缺少 text")
    try:
        with httpx.Client(timeout=40.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/say", json={"text": text})
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "error": r.text[:200]}
    if r.status_code >= 400:
        return JSONResponse(data, status_code=r.status_code)
    return data
'''

t = t.rstrip() + route
M.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加 /api/console/say，语法 OK")
