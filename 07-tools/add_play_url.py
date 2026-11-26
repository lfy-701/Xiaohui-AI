"""控制台：新增 /api/music/play_url（按 URL 直接播放，供搜索结果点播）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
m = M.read_text(encoding="utf-8")

if "/api/music/play_url" in m:
    print("已存在")
    sys.exit(0)

code = '''

@app.post("/api/music/play_url")
def api_music_play_url(body: Dict[str, Any]):
    """按音频 URL 直接播放（搜索结果点播用）。"""
    url = str((body or {}).get("url") or "").strip()
    title = str((body or {}).get("title") or "")
    artist = str((body or {}).get("artist") or "")
    if not url.startswith("http"):
        raise HTTPException(400, "缺少合法的 url")
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    _cache_base = os.getenv("AUDIO_CACHE_BASE", "http://<你的服务器局域网IP>:8106")
    if _cache_base:
        import urllib.parse as _up
        url = _cache_base.rstrip("/") + "/audio?src=" + _up.quote(url, safe="")

    if not _wait_device_online(12.0):
        return {"ok": False, "error": "设备未在线，请先唤醒设备"}

    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    data["song"] = {"name": title, "artist": artist}
    store.add_log("system", "设备播放音乐：" + (title or url[:40]))
    return data
'''

m = m.rstrip() + code
M.write_text(m, encoding="utf-8")
ast.parse(m)
print("已加 /api/music/play_url")
