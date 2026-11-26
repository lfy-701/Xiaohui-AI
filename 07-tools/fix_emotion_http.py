"""表情切换改用控制台硬件接口（已验证 executed），替换 MCP 直连。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
t = F.read_text(encoding="utf-8")

start = t.find("async def _set_emotion(conn, emotion: str")
end = t.find("class ConsoleActionHandler")
if start < 0 or end < 0:
    print("⚠ 未找到替换区间")
    sys.exit(1)

new = '''async def _set_emotion(conn, emotion: str, timeout: float = 5.0):
    """切换设备表情：走控制台硬件接口（已验证可用），失败不影响播放。"""
    import os as _os

    import httpx as _httpx

    base = _os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")
    token = ""
    try:
        with _httpx.Client(timeout=timeout) as c:
            devs = c.get(base + "/api/hardware/devices",
                         headers={"X-Hardware-Token": token}).json().get("devices") or []
            if not devs:
                return
            did = devs[0]["id"]
            c.post(
                f"{base}/api/hardware/devices/{did}/commands",
                headers={"X-Hardware-Token": token},
                json={"type": "emotion", "params": {"emotion": emotion}},
            )
        try:
            conn.logger.bind(tag="Play").info(f"表情切换: {emotion}")
        except Exception:
            pass
    except Exception as e:
        try:
            conn.logger.bind(tag="Play").warning(f"表情切换失败: {e}")
        except Exception:
            pass


'''

t = t[:start] + new + t[end:]
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已改为 HTTP 路径；语法 OK")
