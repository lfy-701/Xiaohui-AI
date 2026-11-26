"""修复音乐健康接口：改用端口探测，并提供 /api/health/music 别名。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

old = '''@app.get("/api/music/health")
def api_music_health(request: Request):
    return {"base": MUSIC_BASE_URL, "ok": True}'''

new = '''def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    import socket as _s

    try:
        with _s.create_connection((host, port), timeout) as s:
            s.close()
        return True
    except Exception:
        return False


@app.get("/api/health/music")
def api_health_music(request: Request):
    """音乐服务健康：直接探测 8102 端口。"""
    return {"ok": _port_open("127.0.0.1", 8102), "base": MUSIC_BASE_URL}


@app.get("/api/music/health")
def api_music_health(request: Request):
    """兼容旧路径，内部转给端口探测。"""
    return {"ok": _port_open("127.0.0.1", 8102), "base": MUSIC_BASE_URL}'''

if old in t:
    t = t.replace(old, new, 1)
    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已重写音乐健康接口；语法 OK")
else:
    print("⚠ 未匹配旧实现")
