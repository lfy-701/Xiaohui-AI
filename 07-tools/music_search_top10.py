"""音乐搜索：默认返回 10 条，按「热度」排序。

iTunes 接口本身没有热度字段，这里用可解释的近似排序：
1) 歌名与关键词完全一致优先
2) 歌名包含关键词优先
3) 其余保持 iTunes 原始相关度顺序（iTunes 本身就按热门程度排）
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = F.read_text(encoding="utf-8")

old = '''@app.get("/api/music/search")
def api_music_search(q: str = "", limit: int = 5):
    if not q.strip():
        return {"ok": False, "songs": [], "error": "关键词为空"}
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(f"{MUSIC_BASE}/rest/search", params={"q": q, "limit": limit})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")'''

new = '''@app.get("/api/music/search")
def api_music_search(q: str = "", limit: int = 10):
    """搜索歌曲，默认 10 条，按热度近似排序。"""
    q = (q or "").strip()
    if not q:
        return {"ok": False, "songs": [], "error": "关键词为空"}
    limit = max(1, min(int(limit or 10), 30))
    try:
        # 多取一些再排序，保证结果质量
        with httpx.Client(timeout=30.0) as c:
            r = c.get(f"{MUSIC_BASE}/rest/search",
                      params={"q": q, "limit": min(limit * 3, 60)})
            r.raise_for_status()
            data = r.json() or {}
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")

    songs = list(data.get("songs") or [])
    key = q.lower()

    def _heat(song):
        title = str(song.get("title") or "").lower()
        if title == key:
            return 0
        if title.startswith(key):
            return 1
        if key in title:
            return 2
        return 3

    # 稳定排序：同档内保持 iTunes 原始相关度（越靠前越热门）
    songs = [s for _, s in sorted(enumerate(songs), key=lambda x: (_heat(x[1]), x[0]))]
    data["songs"] = songs[:limit]
    data["total"] = len(data["songs"])
    return data'''

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("搜索接口已升级：默认 10 条 + 热度近似排序")
else:
    print("⚠ 未匹配搜索接口")
