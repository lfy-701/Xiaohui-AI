"""把 8106 音频转码转发合并进控制台（8080/audio），少维护一个进程。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if '"/audio"' in t or "@app.get('/audio')" in t:
    print("已存在")
    sys.exit(0)

code = '''

# ---------------------------------------------------------------- 音频转码转发
# 设备只需要能访问控制台（局域网可达），由控制台转给成员 A 的 8106。
AUDIO_UPSTREAM = os.getenv("AUDIO_UPSTREAM", "http://<本地模型服务器IP>:8106")


@app.get("/audio")
def audio_proxy(src: str = ""):
    """按 iTunes 试听地址取转码后的 MP3（24kHz 单声道）。"""
    if not src.startswith("http"):
        raise HTTPException(400, "缺少合法的 src")
    params = {"src": src}
    try:
        req = httpx.get(
            AUDIO_UPSTREAM.rstrip("/") + "/audio",
            params=params,
            timeout=60.0,
            follow_redirects=True,
        )
    except Exception as e:
        raise HTTPException(502, f"音频转码不可用：{e}")
    if req.status_code != 200:
        raise HTTPException(req.status_code, req.text[:200])
    return Response(
        content=req.content,
        media_type=req.headers.get("content-type", "audio/mpeg"),
        headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"},
    )


@app.get("/audio/health")
def audio_health():
    """转码链路是否健康。"""
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(AUDIO_UPSTREAM.rstrip("/") + "/health")
        return {"ok": r.status_code == 200, "upstream": AUDIO_UPSTREAM,
                "status": r.status_code}
    except Exception as e:
        return {"ok": False, "upstream": AUDIO_UPSTREAM, "error": str(e)}
'''

t = t.rstrip() + code
M.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加 /audio 转发与健康检查")
