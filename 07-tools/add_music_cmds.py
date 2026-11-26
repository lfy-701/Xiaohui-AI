"""设备音乐能力：点歌 / 推荐 / 查询可点歌曲 / 停止播放。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = F.read_text(encoding="utf-8")

if "_handle_music_cmd" in t:
    print("已存在")
    sys.exit(0)

helper = '''

# ---------------- 音乐能力：点歌 / 推荐 / 查询 / 停止 ----------------
_STOP_WORDS = ("别放了", "停止播放", "停一下", "关掉音乐", "关音乐", "暂停", "别唱了", "安静")
_LIST_WORDS = ("有什么歌", "有哪些歌", "能听什么", "歌单", "都有什么歌")
_REC_WORDS = ("推荐一首", "推荐首歌", "随便放", "来点音乐", "放点音乐", "随机播放",
              "随便来首", "有什么好听", "放首歌", "听点歌")


async def _handle_music_cmd(conn, text: str) -> bool:
    """处理音乐类指令；已处理返回 True。"""
    if not text:
        return False
    t = text.strip()

    # 1) 停止
    if any(w in t for w in _STOP_WORDS):
        conn.client_abort = True
        conn.logger.bind(tag=TAG).info("音乐：收到停止指令")
        try:
            await _speak_ack(conn, "好，停了。")
        except Exception:
            pass
        return True

    # 2) 查询可点歌曲
    if any(w in t for w in _LIST_WORDS):
        conn.logger.bind(tag=TAG).info("音乐：查询可点歌曲")
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get("http://127.0.0.1:8080/api/music/search",
                                params={"q": "热门", "limit": 3})
                songs = (r.json() or {}).get("songs") or []
            names = "、".join(str(s.get("title") or "") for s in songs[:3])
            msg = f"现在可以点这些：{names}。想听哪首？" if names else "暂时没查到能放的歌。"
            await _speak_ack(conn, msg)
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"查询歌曲失败: {e}")
        return True

    # 3) 推荐 / 随机
    if any(w in t for w in _REC_WORDS) and not any(w in t for w in ("播放", "放一", "放首", "来一首")):
        conn.logger.bind(tag=TAG).info("音乐：推荐并播放")
        try:
            import httpx

            await _speak_ack(conn, "好，给你放首轻音乐。")
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post("http://127.0.0.1:8080/api/music/play_device",
                                 json={"query": "轻音乐"})
                d = r.json()
            return bool(d.get("ok"))
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"推荐播放失败: {e}")
            return False

    # 4) 点播指定歌曲（沿用原逻辑）
    return False


'''

idx = t.find("async def _try_play_music")
if idx < 0:
    print("⚠ 未找到插入点")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 调用点：先走音乐指令，再走点歌
old = '''    try:
        if await _try_play_music(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"点歌判断异常: {e}")'''
new = '''    try:
        if await _handle_music_cmd(conn, text):
            return
        if await _try_play_music(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"音乐指令异常: {e}")'''

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已加音乐指令：点歌/推荐/查询/停止")
else:
    print("⚠ 未找到调用点")
