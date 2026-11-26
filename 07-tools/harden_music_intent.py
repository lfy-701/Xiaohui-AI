"""点歌逻辑加固：放宽匹配 + 失败回退正常对话。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

R = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = R.read_text(encoding="utf-8")

start = t.find("def _parse_music_query(text: str):")
end = t.find("async def handleAudioMessage")
if start < 0 or end < 0:
    print("⚠ 锚点未找到")
    sys.exit(1)

new = '''def _parse_music_query(text: str):
    """识别点歌意图，返回歌名；不是点歌返回 None。"""
    if not text:
        return None
    t = text.strip()

    # 明确说了「歌/曲/音乐」的，即使动词听错也当点歌
    if any(k in t for k in ("音乐", "歌曲", "首歌", "放歌", "听歌")):
        q = t
        for w in ("播放", "放一首", "放首", "来一首", "来首", "我想听", "想听", "放点", "听点", "放"):
            if w in q:
                q = q.split(w, 1)[1]
                break
        q = _re.sub(r"[。！？!?，,、~～\\s]+$", "", q)
        q = _re.sub(r"(的歌|音乐|歌曲|歌儿|首歌|歌|吧|呗|呀|啊)$", "", q).strip()
        return q

    # 常规动词匹配
    for w in ("播放", "放一首", "放首", "放个", "来一首", "来首", "我想听", "想听一首", "想听"):
        if w in t:
            q = t.split(w, 1)[1].strip()
            q = _re.sub(r"[。！？!?，,、~～\\s]+$", "", q)
            q = _re.sub(r"(的歌|音乐|歌曲|歌儿|吧|呗|呀|啊)$", "", q).strip()
            return q

    # 识别容易把「放首」听成「放肆/放四/放个」，兜一层
    m = _re.match(r"^(?:放肆|放四|放似|放个|放歌)(.+)$", t)
    if m:
        q = _re.sub(r"[。！？!?，,、~～\\s]+$", "", m.group(1)).strip()
        if q:
            return q
    return None


async def _try_play_music(conn, text: str) -> bool:
    """命中点歌意图且播放成功时返回 True；失败返回 False 交给正常对话。"""
    q = _parse_music_query(text)
    if q is None:
        return False
    conn.logger.bind(tag=TAG).info(f"识别到点歌意图：{q or '（随机）'}")
    try:
        import httpx

        base = "http://127.0.0.1:8080"
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{base}/api/music/play_device",
                             json={"query": q or "轻音乐"})
            d = r.json()
        ok = bool(d.get("ok"))
        song = ((d.get("song") or {}).get("name") or q or "音乐")
        conn.logger.bind(tag=TAG).info(f"点歌结果：ok={ok} song={song} raw={str(d)[:120]}")
        if not ok:
            conn.logger.bind(tag=TAG).warning("点歌失败，回退正常对话")
        return ok
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"点歌异常，回退正常对话: {e}")
        return False


'''

t = t[:start] + new + t[end:]
R.write_text(t, encoding="utf-8")
ast.parse(t)
print("点歌逻辑已加固")
