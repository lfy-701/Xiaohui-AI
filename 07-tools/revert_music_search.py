"""撤回音乐搜索的 10 条 + 热度排序，恢复原样。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
lines = F.read_text(encoding="utf-8").split("\n")

start = end = None
for i, ln in enumerate(lines):
    if ln.strip() == '@app.get("/api/music/search")':
        start = i
    elif start is not None and ln.startswith("@app.get(") or (start is not None and ln.startswith("@app.post(")):
        end = i
        break

if start is None:
    print("⚠ 未找到搜索接口")
    sys.exit(1)
if end is None:
    # 兜底：找下一个空行后的装饰器
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("@app."):
            end = i
            break

new = '''@app.get("/api/music/search")
def api_music_search(q: str = "", limit: int = 5):
    if not q.strip():
        return {"ok": False, "songs": [], "error": "关键词为空"}
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(f"{MUSIC_BASE}/rest/search", params={"q": q, "limit": limit})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")
'''.split("\n")

lines[start:end] = new
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("搜索接口已恢复（limit=5）；语法 OK")

# 前端改回 5
C = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
t = C.read_text(encoding="utf-8")
if "limit=10" in t:
    C.write_text(t.replace("limit=10", "limit=5"), encoding="utf-8")
    print("前端已改回 5 条")
