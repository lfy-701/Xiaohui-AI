"""播放音乐时显示「享受音乐」表情，播完/停止后恢复。

实现：MCP self.set_emotion（设备端，仅在播放前后各调一次，不影响推流）
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

if "MUSIC_EMOTION" in t:
    print("已存在")
    sys.exit(0)

# 1) 工具函数
helper = '''

MUSIC_EMOTION = "love"        # 享受音乐的表情
DEFAULT_EMOTION = "neutral"   # 恢复用


async def _set_emotion(conn, emotion: str, timeout: float = 3.0):
    """切换设备表情（失败静默，不影响播放）。"""
    import json as _json

    try:
        from core.providers.tools.device_mcp import call_mcp_tool

        await asyncio.wait_for(
            call_mcp_tool(conn, conn.mcp_client, "self.set_emotion",
                          _json.dumps({"emotion": emotion}, ensure_ascii=False),
                          timeout=int(timeout)),
            timeout=timeout,
        )
        conn.logger.bind(tag="Play").info(f"表情切换: {emotion}")
    except Exception:
        pass

'''

idx = t.find("class ConsoleActionHandler")
if idx < 0:
    print("⚠ 未找到类定义")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 2) 播放开始前设表情（在 tts start 之前）
old_start = '''                conn.client_abort = False
                await send_tts_message(conn, "start")'''
new_start = '''                conn.client_abort = False
                # 播放前：切到「享受音乐」表情
                await _set_emotion(conn, MUSIC_EMOTION)
                await send_tts_message(conn, "start")'''
if old_start in t:
    t = t.replace(old_start, new_start, 1)
    print("已插入：播放前设为享受音乐表情")
else:
    print("⚠ 未匹配 tts start 位置")

# 3) 播完恢复表情（finally 里，保证中断也恢复）
old_fin = '''            finally:
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)'''
new_fin = '''            finally:
                # 播放结束（含被打断）：恢复默认表情
                await _set_emotion(conn, DEFAULT_EMOTION)
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)'''
if old_fin in t:
    t = t.replace(old_fin, new_fin, 1)
    print("已插入：结束后恢复表情")
else:
    print("⚠ 未匹配 finally 位置")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
