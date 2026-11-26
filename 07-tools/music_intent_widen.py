"""放宽音乐意图匹配 + 播放失败也要回应，不再落到模型闲聊。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = F.read_text(encoding="utf-8")

# 1) 放宽「推荐/泛听」关键词
old_rec = '''_REC_WORDS = ("推荐一首", "推荐首歌", "随便放", "来点音乐", "放点音乐", "随机播放",
              "随便来首", "有什么好听", "放首歌", "听点歌")'''
new_rec = '''_REC_WORDS = ("推荐一首", "推荐首歌", "随便放", "来点音乐", "放点音乐", "随机播放",
              "随便来首", "有什么好听", "放首歌", "听点歌", "放首歌", "放音乐", "听歌",
              "想听歌", "放首曲子", "来首歌", "放个歌", "唱首歌", "来一段音乐", "播放音乐")'''

if old_rec in t:
    t = t.replace(old_rec, new_rec, 1)

# 2) 泛听时也要有明确回应，失败不说没放
old_body = '''        try:
            import httpx

            await _speak_ack(conn, "好，给你放首轻音乐。")
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post("http://127.0.0.1:8080/api/music/play_device",
                                 json={"query": "轻音乐"})
                d = r.json()
            return bool(d.get("ok"))
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"推荐播放失败: {e}")
            return False'''

new_body = '''        try:
            import httpx

            await _speak_ack(conn, "好，给你放首轻音乐。")
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post("http://127.0.0.1:8080/api/music/play_device",
                                 json={"query": "轻音乐"})
                d = r.json()
            if not d.get("ok"):
                conn.logger.bind(tag=TAG).warning(f"推荐播放未成功: {d}")
                await _speak_ack(conn, "这会儿放不出来，等一下再试试。")
            # 无论成功与否都算已处理，避免落到模型闲聊
            return True
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"推荐播放失败: {e}")
            await _speak_ack(conn, "这会儿放不出来，等一下再试试。")
            return True'''

if old_body in t:
    t = t.replace(old_body, new_body, 1)

# 3) 点播失败也回应，不落到模型
old_play = '''        if not ok:
            conn.logger.bind(tag=TAG).warning("点歌失败，回退正常对话")
        return ok'''
new_play = '''        if not ok:
            conn.logger.bind(tag=TAG).warning("点歌失败")
            await _speak_ack(conn, "没找到这首，换一首试试？")
        return True'''

if old_play in t:
    t = t.replace(old_play, new_play, 1)

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已放宽匹配并补上失败回应")
