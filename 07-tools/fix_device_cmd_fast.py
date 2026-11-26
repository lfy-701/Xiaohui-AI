"""执行设备指令后：优先 MCP 直连（快），并确保回到聆听（发 tts stop）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
lines = F.read_text(encoding="utf-8").split("\n")

start = next(i for i, ln in enumerate(lines) if ln.startswith("async def _handle_device_cmd"))
end = next(i for i, ln in enumerate(lines) if ln.startswith("async def _handle_music_cmd"))

NEW = '''async def _handle_device_cmd(conn, text: str) -> bool:
    """灯珠 / 灯光秀 / 动作：MCP 直连优先，执行完立刻回到聆听（不播报）。"""
    import json as _json
    import os as _os

    import httpx as _httpx

    t = (text or "").strip()
    if not t or len(t) > 40:
        return False

    base = _os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")
    token = ""

    LED_COLORS = {
        "红": "red", "绿": "green", "蓝": "blue", "黄": "yellow",
        "紫": "purple", "青": "cyan", "粉": "pink", "橙": "orange", "白": "white",
    }

    kind = action = None          # kind: action / pose / led / effect
    value = ""

    # ---------- 灯 ----------
    if any(k in t for k in ("灯", "灯珠", "发光")):
        if any(k in t for k in ("灯光秀", "彩虹", "彩灯", "跑马", "灯效")):
            kind, value = "effect", "rainbow"
        elif "呼吸" in t:
            kind, value = "effect", "breathing"
        elif "闪" in t:
            kind, value = "effect", "blink"
        elif "流水" in t:
            kind, value = "effect", "chase"
        elif any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            kind, value = "led", "off"
        else:
            for kw, name in LED_COLORS.items():
                if kw in t:
                    kind, value = "led", name
                    break
            if kind is None:
                kind, value = "led", "warm"

    # ---------- 动作 ----------
    if kind is None:
        actions = {
            "坐下": "sit", "坐": "sit",
            "趴下": "lie", "趴": "lie",
            "跳舞": "dance",
            "站起来": "stand", "起身": "stand",
            "前进": "walk", "往前走": "walk",
            "后退": "back", "往后退": "back",
            "左转": "left", "右转": "right",
            "摇尾巴": "wag", "摇摇头": "shake",
            "停下": "stop",
        }
        for word, act in actions.items():
            if word in t:
                kind, action = "action", act
                break

    if kind is None:
        return False

    # ---------- 1) MCP 直连（最快） ----------
    done = False
    try:
        from core.providers.tools.device_mcp import call_mcp_tool

        if kind == "action":
            await call_mcp_tool(conn, conn.mcp_client, "self.dog_action",
                                _json.dumps({"action": action}), timeout=4)
            done = True
        elif kind == "led":
            await call_mcp_tool(conn, conn.mcp_client, "self.set_led",
                                _json.dumps({"color": value}), timeout=4)
            done = True
        elif kind == "effect":
            await call_mcp_tool(conn, conn.mcp_client, "self.led_effect",
                                _json.dumps({"effect": value}), timeout=4)
            done = True
    except Exception:
        done = False

    # ---------- 2) 失败则走控制台心跳队列（自定义姿态也在这里） ----------
    if not done:
        try:
            with _httpx.Client(timeout=8.0) as c:
                devs = c.get(base + "/api/hardware/devices",
                             headers={"X-Hardware-Token": token}).json().get("devices") or []
                if devs:
                    did = devs[0]["id"]
                    if kind == "action":
                        try:
                            saved = c.get(base + "/api/hardware/actions",
                                          headers={"X-Hardware-Token": token}).json().get("actions") or {}
                            angles = saved.get(action)
                        except Exception:
                            angles = None
                        if angles:
                            c.post(f"{base}/api/hardware/devices/{did}/commands",
                                   headers={"X-Hardware-Token": token},
                                   json={"type": "pose", "params": {"value": angles}})
                        else:
                            c.post(f"{base}/api/hardware/devices/{did}/commands",
                                   headers={"X-Hardware-Token": token},
                                   json={"type": "action", "params": {"value": action}})
                    elif kind == "led":
                        rgb = {"red": "255,0,0", "green": "0,200,0", "blue": "0,0,255",
                               "yellow": "255,200,0", "purple": "180,0,255",
                               "cyan": "0,220,200", "pink": "255,80,160",
                               "orange": "255,120,0", "white": "255,255,255",
                               "off": "0,0,0", "warm": "255,200,0"}.get(value, "255,200,0")
                        c.post(f"{base}/api/hardware/devices/{did}/commands",
                               headers={"X-Hardware-Token": token},
                               json={"type": "led", "params": {"value": rgb}})
                    else:
                        c.post(f"{base}/api/hardware/devices/{did}/commands",
                               headers={"X-Hardware-Token": token},
                               json={"type": "led", "params": {"value": value}})
        except Exception:
            pass

    # ---------- 3) 关键：发 tts stop，让设备从"说话"回到"聆听" ----------
    try:
        from core.handle.sendAudioHandle import send_tts_message

        await send_tts_message(conn, "stop")
        conn.client_is_speaking = False
        try:
            conn.clearSpeakStatus()
        except Exception:
            pass
    except Exception:
        pass

    return True


'''

lines[start:end] = NEW.split("\n")
F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("已重写 _handle_device_cmd：MCP 直连 + 执行后回聆听")
