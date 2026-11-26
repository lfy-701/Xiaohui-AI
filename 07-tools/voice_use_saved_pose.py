"""动作严格按在线互动网页保存的姿态执行：
先查控制台 /api/hardware/actions（缓存 60 秒），命中就用 set_servo 逐路设定，
没命中才用固件默认动作。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = F.read_text(encoding="utf-8")

# 1) 加缓存与取姿态函数（放在 _handle_device_cmd 前）
if "_saved_actions" not in t:
    HELPER = '''_saved_actions_cache = {"at": 0.0, "data": {}}


async def _get_saved_actions(base: str, token: str) -> dict:
    """取控制台保存的自定义动作（60 秒缓存）。"""
    import time as _t

    import httpx as _hx

    now = _t.time()
    if now - _saved_actions_cache["at"] < 60 and _saved_actions_cache["data"]:
        return _saved_actions_cache["data"]
    try:
        with _hx.Client(timeout=6.0) as c:
            data = c.get(base + "/api/hardware/actions",
                         headers={"X-Hardware-Token": token}).json().get("actions") or {}
        _saved_actions_cache["at"] = now
        _saved_actions_cache["data"] = data
        return data
    except Exception:
        return _saved_actions_cache["data"]


async def _apply_pose(conn, angles: str) -> bool:
    """把 "90,50,90,121" 逐路写进舵机（MCP 直连）。"""
    import json as _json

    from core.providers.tools.device_mcp import call_mcp_tool

    try:
        parts = [int(x) for x in str(angles).replace(" ", "").split(",") if x.strip() != ""]
    except Exception:
        return False
    if len(parts) < 4:
        return False

    ok = False
    for i, ang in enumerate(parts[:4]):
        try:
            await call_mcp_tool(conn, conn.mcp_client, "self.set_servo",
                                _json.dumps({"servo": i, "angle": ang}), timeout=3)
            ok = True
        except Exception:
            pass
    return ok


'''
    idx = t.find("async def _handle_device_cmd")
    t = t[:idx] + HELPER + t[idx:]

# 2) 动作分支：先查自定义姿态
old = '''    # ---------- 1) MCP 直连（最快） ----------
    done = False
    try:
        from core.providers.tools.device_mcp import call_mcp_tool

        if kind == "action":
            await call_mcp_tool(conn, conn.mcp_client, "self.dog_action",
                                _json.dumps({"action": action}), timeout=4)
            done = True'''

new = '''    # ---------- 1) MCP 直连（最快） ----------
    done = False
    try:
        from core.providers.tools.device_mcp import call_mcp_tool

        if kind == "action":
            # 严格按网页保存的姿态执行
            saved = await _get_saved_actions(base, token)
            angles = saved.get(action) if saved else None
            if angles:
                done = await _apply_pose(conn, angles)
                conn.logger.bind(tag=TAG).info(f"动作 {action} 使用自定义姿态 {angles}")
            if not done:
                await call_mcp_tool(conn, conn.mcp_client, "self.dog_action",
                                    _json.dumps({"action": action}), timeout=4)
                conn.logger.bind(tag=TAG).info(f"动作 {action} 使用固件默认")
                done = True'''

if old in t:
    t = t.replace(old, new, 1)
    print("已改为：动作优先使用网页保存的姿态")
else:
    print("⚠ 动作分支未匹配")

F.write_text(t, encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("语法 OK")
