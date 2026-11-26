"""P0：知识库接入语音 + 控制台健康检查接口。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ============ 1) 语音服务：知识库检索直通 ============
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

if "_handle_kb_cmd" not in v:
    KB = '''import os as _os_kb

_KB_URL = _os_kb.getenv("KB_URL", "http://127.0.0.1:8077").rstrip("/")
_KB_WORDS = ("知识库", "课本", "教材", "课文", "书里", "第几单元", "这个知识点",
             "资料里", "文档里", "讲过", "学过")


async def _handle_kb_cmd(conn, text: str) -> bool:
    """知识库类问题：检索后直接播报要点（不经过大模型，快且不编）。"""
    import httpx as _hx

    t = (text or "").strip()
    if not t or not any(w in t for w in _KB_WORDS):
        return False

    query = t
    for w in ("知识库", "帮我查", "查一下", "查查", "请", "一下"):
        query = query.replace(w, " ")
    query = " ".join(query.split()) or t

    hits = []
    try:
        with _hx.Client(timeout=8.0) as c:
            r = c.post(_KB_URL + "/kb/search", json={"query": query, "top_k": 3})
            hits = (r.json() or {}).get("hits") or []
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"知识库检索失败: {e}")
        return False

    if not hits:
        await _speak_ack(conn, "这个我知识库里还没有资料，你可以先在控制台的知"
                              "识库页面把课本内容加进去。")
        return True

    parts = []
    for h in hits[:3]:
        txt = (h.get("text") or h.get("content") or "").strip().replace("\\n", " ")
        if txt:
            parts.append(txt[:120])
    if not parts:
        return False

    say = "我在资料里找到这些：" + "；".join(parts) + "。"
    if len(say) > 320:
        say = say[:320] + "。"
    await _speak_ack(conn, say)
    conn.logger.bind(tag=TAG).info(f"知识库回答 {len(hits)} 条命中")
    return True


'''
    idx = v.find("async def _handle_query_cmd")
    if idx > 0:
        v = v[:idx] + KB + v[idx:]
    # 接入调度（放在天气/新闻之后）
    old = '''    # 首先进行意图分析
    intent_handled = await handle_user_intent(conn, text)'''
    new = '''    # 知识库直通
    try:
        if await _handle_kb_cmd(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"知识库直通异常: {e}")

    # 首先进行意图分析
    intent_handled = await handle_user_intent(conn, text)'''
    if old in v:
        v = v.replace(old, new, 1)
        print("语音：知识库直通已接入")
    V.write_text(v, encoding="utf-8")
    ast.parse(v)

# ============ 2) 控制台：健康检查 ============
C = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = C.read_text(encoding="utf-8")

if "/api/health" not in c:
    HEALTH = '''

@app.get("/api/health")
def api_health(request: Request):
    """汇总健康检查：各服务是否在线 + 关键参数。"""
    import httpx as _hx

    targets = {
        "语音接口": "http://127.0.0.1:8003/health",
        "语音服务": "http://127.0.0.1:8000/",
        "大模型专区": "http://127.0.0.1:8013/health",
        "知识库": "http://127.0.0.1:8077/health",
        "音乐服务": "http://127.0.0.1:8102/health",
    }
    out = {"console": "ok", "services": {}}
    for name, url in targets.items():
        try:
            r = _hx.get(url, timeout=3)
            out["services"][name] = "ok" if r.status_code < 500 else f"http {r.status_code}"
        except Exception:
            out["services"][name] = "down"

    try:
        out["device_online"] = len(_ws_clients())
    except Exception:
        out["device_online"] = None
    out["ok"] = all(v == "ok" for v in out["services"].values())
    return out


@app.get("/api/music/health")
def api_music_health(request: Request):
    return {"base": MUSIC_BASE_URL, "ok": True}
'''
    c = c.rstrip() + HEALTH
    C.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("控制台：已加 /api/health 与 /api/music/health")
