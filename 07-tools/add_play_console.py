"""控制台：新增 /api/music/play_device。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "music/play_device" in t:
    print("已存在")
    sys.exit(0)

route = '''

@app.post("/api/music/play_device")
def api_music_play_device(body: Dict[str, Any]):
    """搜索并让设备播放第一首（30 秒试听）。"""
    query = str((body or {}).get("query") or "").strip()
    if not query:
        raise HTTPException(400, "缺少 query")
    base = os.getenv("MUSIC_BASE_URL", "http://127.0.0.1:8102")
    try:
        with httpx.Client(timeout=20.0) as c:
            r = c.get(f"{base}/rest/search", params={"query": query, "limit": 3})
            songs = (r.json() or {}).get("songs") or []
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")
    if not songs:
        return {"ok": False, "error": "没有找到带试听音源的歌曲"}
    song = songs[0]
    url = song.get("preview_url")
    if not url:
        return {"ok": False, "error": "这首没有试听音源"}
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    data["song"] = {"name": song.get("name"), "artist": song.get("artist")}
    store.add_log("system", "设备播放音乐：" + str(song.get("name")))
    return data
'''

t = t.rstrip() + route
M.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加 /api/music/play_device，语法 OK")
