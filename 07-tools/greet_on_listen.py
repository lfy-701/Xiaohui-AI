"""唤醒应答改为「开始聆听即应答」，不再依赖 ASR 识别到唤醒词。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\textHandle.py")
t = F.read_text(encoding="utf-8")

if "_greet_on_listen" in t:
    print("已存在")
    sys.exit(0)

helper = '''

# ---------------- 唤醒应答：开始聆听就回一句 ----------------
async def _greet_on_listen(conn):
    """设备一进入聆听（用户喊了唤醒词）就播一句应答。

    不依赖 ASR 是否识别到唤醒词——设备端唤醒词是本地的，
    「你好小慧」这几个字不会被送到服务端。
    """
    import time as _time

    now = _time.time()
    last = getattr(conn, "_last_greet_at", 0)
    if now - last < 2.5:          # 防抖：同一次唤醒只播一次
        return
    conn._last_greet_at = now

    try:
        from core.handle.sendAudioHandle import sendAudioMessage
        from core.providers.tts.dto.dto import SentenceType
        from core.utils.util import audio_to_data

        from core.handle.helloHandle import wakeup_words_config

        voice = "zh-CN-XiaoxiaoNeural"
        try:
            from core.utils.voice_settings import load as _load_rt
            voice = (_load_rt().get("voice") or voice)
        except Exception:
            pass

        response = wakeup_words_config.get_wakeup_response(voice)
        if not response or not response.get("file_path"):
            response = {"text": "我在呢，你说。",
                        "file_path": "config/assets/wakeup_words.wav"}

        packets, _ = audio_to_data(response.get("file_path"))
        if not packets:
            return
        conn.logger.bind(tag=TAG).info(f"唤醒应答（聆听触发）: {response.get('text')}")
        conn.client_abort = False
        await sendAudioMessage(conn, SentenceType.FIRST, packets, response.get("text"))
        await sendAudioMessage(conn, SentenceType.LAST, [], None)
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"唤醒应答失败: {e}")


'''

idx = t.find("async def handleTextMessage")
if idx < 0:
    print("⚠ 未找到入口")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在 listen start 分支触发（放到预热 TTS 那段之后）
old = '''              if msg_json["state"] == "start":
                  conn.client_have_voice = True
                  conn.client_voice_stop = False'''
new = '''              if msg_json["state"] == "start":
                  conn.client_have_voice = True
                  conn.client_voice_stop = False
                  # 用户刚喊了唤醒词：立刻回一句
                  try:
                      import asyncio as _aio
                      _aio.create_task(_greet_on_listen(conn))
                  except Exception:
                      pass'''

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已加聆听触发应答")
else:
    print("⚠ 未找到 listen start 分支")
