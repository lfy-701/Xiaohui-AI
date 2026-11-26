"""语音点歌：识别到点歌意图时直接播放，跳过模型。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

R = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = R.read_text(encoding="utf-8")

if "_try_play_music" in t:
    print("已存在")
    sys.exit(0)

helper = '''

# ---------------- 语音点歌（关键词直通，跳过模型） ----------------
import re as _re


def _parse_music_query(text: str):
    """识别点歌意图，返回歌名；不是点歌返回 None。"""
    if not text:
        return None
    t = text.strip()
    for w in ("播放", "放一首", "放首", "放个", "来一首", "来首", "我想听", "想听一首", "想听", "唱一首"):
        if w in t:
            q = t.split(w, 1)[1].strip()
            q = _re.sub(r"[。！？!?，,、~～\\s]+$", "", q)
            q = _re.sub(r"(的歌|音乐|歌曲|歌儿|吧|呗|呀|啊)$", "", q).strip()
            return q
    return None


async def _try_play_music(conn, text: str) -> bool:
    """命中点歌意图时直接调控制台播放，返回是否已处理。"""
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
        song = ((d.get("song") or {}).get("name") or q or "音乐")
        conn.logger.bind(tag=TAG).info(f"点歌结果：ok={d.get('ok')} song={song}")
        return True
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"点歌失败: {e}")
        return False


'''

idx = t.find("async def handleAudioMessage")
if idx < 0:
    print("⚠ 未找到 handleAudioMessage")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在调用大模型之前插入点歌判断
old = "    conn.executor.submit(conn.chat, text)"
new = '''    # 点歌意图直通：不经过大模型，直接播放
    try:
        if await _try_play_music(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"点歌判断异常: {e}")

    conn.executor.submit(conn.chat, text)'''

if old in t:
    t = t.replace(old, new, 1)
    R.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已挂接点歌直通")
else:
    print("⚠ 未找到 chat 调用点")
