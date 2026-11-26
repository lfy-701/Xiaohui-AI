"""语音点歌：识别到「放首歌/来一首 X」后直接调控制台播放，不等模型。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\textHandle.py")
t = F.read_text(encoding="utf-8")

if "music_intent" in t:
    print("已存在")
    sys.exit(0)

helper = '''

# ---------------- 语音点歌（关键词直通） ----------------
import re as _re


def _parse_music_query(text: str):
    """识别点歌意图，返回歌名（可能为空字符串）。"""
    if not text:
        return None
    t = text.strip()
    for w in ("播放", "放一首", "放首", "放个", "来一首", "来首", "我想听", "想听", "放点", "听一下"):
        if w in t:
            q = t.split(w, 1)[1].strip()
            q = _re.sub(r"[。！？!?，,、\s]+$", "", q)
            q = _re.sub(r"(的歌|音乐|歌曲|吧|呗|呀|啊)$", "", q).strip()
            return q
    return None


async def _try_play_music(conn, text: str) -> bool:
    """命中点歌意图时，直接调控制台播放，返回是否已处理。"""
    q = _parse_music_query(text)
    if q is None:
        return False
    conn.logger.bind(tag=TAG).info(f"识别到点歌意图，歌名：{q or '（随机）'}")
    try:
        import httpx

        base = "http://127.0.0.1:8080"
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{base}/api/music/play_device",
                             json={"query": q or "轻音乐"})
            d = r.json()
        ok = bool(d.get("ok"))
        song = (d.get("song") or {}).get("name") or (q or "音乐")
        conn.logger.bind(tag=TAG).info(f"点歌结果：{d}")
        # 用 TTS 回一句，让用户知道开始了
        msg = f"好，这就放《{song}》给你听。" if ok else "没找到这首，换一首试试？"
        await conn.tts_to_speak(msg) if hasattr(conn, "tts_to_speak") else None
        return True
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"点歌失败: {e}")
        return False
'''

# 插入 helper 到文件末尾之前（放在函数外）
idx = t.find("async def handleTextMessage(conn, message):")
if idx < 0:
    print("⚠ 未找到入口函数")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在 listen stop（识别完成）之后挂接：位于 handleAudioMessage 之前最稳妥，
# 改为在 handleTextMessage 处理 listen/stop 分支里先尝试
old = '''                elif msg_json["state"] == "stop":
                    conn.client_have_voice = True
                    conn.client_voice_stop = True
                    if len(conn.asr_audio) > 0:
                        await handleAudioMessage(conn, b"")'''
new = '''                elif msg_json["state"] == "stop":
                    conn.client_have_voice = True
                    conn.client_voice_stop = True
                    if len(conn.asr_audio) > 0:
                        await handleAudioMessage(conn, b"")'''
if old in t:
    pass  # 识别结果在 handleAudioMessage 里，改那边

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已插入点歌解析函数")
