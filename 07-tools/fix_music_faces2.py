"""唱歌表情：只在开头和中段各设一次（共 2 次），不循环刷调用。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

start = t.find("async def _music_faces(conn, stop_flag):")
if start < 0:
    print("⚠ 未找到 _music_faces")
    sys.exit(1)
end = t.find("    async def handle_play(self, request):")
if end < start:
    print("⚠ 未找到结束边界")
    sys.exit(1)

new = '''async def _music_faces(conn, stop_flag):
    """唱歌表情：只设 2 次（开头+中段），不循环，避免拖累连接。"""
    import asyncio as _aio
    import json as _json

    try:
        from core.providers.tools.device_mcp import call_mcp_tool
    except Exception:
        return

    async def _set(expr):
        try:
            await _aio.wait_for(
                call_mcp_tool(conn, conn.mcp_client, "self.face_expression",
                              _json.dumps({"expression": expr}, ensure_ascii=False),
                              timeout=3),
                timeout=3,
            )
            conn.logger.bind(tag="Play").info(f"唱歌表情：{expr}")
        except Exception:
            pass

    # 开头：享受音乐
    await _set("happy")
    # 等 15 秒（可被停止打断）
    for _ in range(150):
        if stop_flag.is_set():
            return
        await _aio.sleep(0.1)
    if not stop_flag.is_set():
        await _set("love")


'''

t = t[:start] + new + t[end:]
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已改为 2 次表情（happy → love）")
