"""修复：长语音播完后卡在聆听（服务端仍以为在说话，导致不收音/唤醒词无效）。

做法：
1) 设备上报 listen start 时，若服务端仍标记在说话 → 复位
2) 加「卡死看门狗」：长时间没有 VAD 命中且标记在说话 → 强制复位并发 stop
3) 故事长度收紧，避免超长播放
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

T = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\textHandle.py")
t = T.read_text(encoding="utf-8")

old = '''            if msg_json["state"] == "start":
                conn.client_have_voice = True
                conn.client_voice_stop = False'''

new = '''            if msg_json["state"] == "start":
                conn.client_have_voice = True
                conn.client_voice_stop = False
                # 设备已回到聆听：清掉服务端残留的说话/唤醒保护状态，
                # 否则长语音播完后会「界面聆听中但听不进去」
                try:
                    if conn.client_is_speaking or getattr(conn, "just_woken_up", False):
                        conn.logger.bind(tag=TAG).info("复位说话/唤醒状态（设备已回到聆听）")
                    conn.client_is_speaking = False
                    conn.just_woken_up = False
                    conn.client_abort = False
                    conn.client_have_voice = False
                    try:
                        conn.asr_audio.clear()
                    except Exception:
                        pass
                    try:
                        conn.clearSpeakStatus()
                    except Exception:
                        pass
                except Exception:
                    pass'''

if old in t and "复位说话/唤醒状态" not in t:
    t = t.replace(old, new, 1)
    T.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("listen start：已加状态复位")
else:
    print("未匹配或已存在")
