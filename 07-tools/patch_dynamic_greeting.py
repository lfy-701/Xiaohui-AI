"""唤醒后改为「大模型现编问候」：每次唤醒都由 LLM 按人设生成一句开场白。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\helloHandle.py")
t = F.read_text(encoding="utf-8")

if "DYNAMIC_GREETING" in t:
    print("已改过")
    sys.exit(0)

old_tail = '''    conn.client_abort = False
    opus_packets, _ = audio_to_data(response.get("file_path"))

    conn.logger.bind(tag=TAG).info(f"播放唤醒词回复: {response.get('text')}")
    await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, response.get("text"))
    await sendAudioMessage(conn, SentenceType.LAST, [], None)

    # 补充对话
    conn.dialogue.put(Message(role="assistant", content=response.get("text")))

    # 检查是否需要更新唤醒词回复
    if time.time() - response.get("time", 0) > WAKEUP_CONFIG["refresh_time"]:
        if not _wakeup_response_lock.locked():
            asyncio.create_task(wakeupWordsResponse(conn))
    return True
'''

new_tail = '''    # DYNAMIC_GREETING: 不再播放固定音频，改由大模型按人设现编一句开场白
    conn.client_abort = False
    try:
        await conn.chat("（用户刚刚喊了唤醒词，请用一句符合你人设的话回应，"
                        "像平常说话一样自然，不要超过 15 个字，不要问太多问题）")
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"动态问候失败，回退固定音频: {e}")
        opus_packets, _ = audio_to_data(response.get("file_path"))
        await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, response.get("text"))
        await sendAudioMessage(conn, SentenceType.LAST, [], None)
    return True
'''

if old_tail in t:
    t = t.replace(old_tail, new_tail, 1)
    F.write_text(t, encoding="utf-8")
    print("已改为动态问候")
else:
    print("⚠ 锚点不匹配")
    sys.exit(1)

import ast
ast.parse(t)
print("语法 OK")
