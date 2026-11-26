"""语音 + 打字 控灯/动作。

设计：统一走控制台已实现的硬件指令接口（X-Hardware-Token 鉴权 → 设备心跳队列），
不碰控制台登录中间件，也不改固件。

- 打字：agent chat 接口里识别「灯/动作」关键词，直接下发并返回话术
- 语音：语音服务本地命令识别后，HTTP 调控制台 /api/hardware/... 下发
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CON = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = CON.read_text(encoding="utf-8")

# ---------------- 控制台：文字解析器 ----------------
if "_device_cmd_from_text" not in c:
    helper = '''

# ---------------------------------------------------------------- 文字 → 设备指令
LED_COLOR_MAP = {
    "红": (255, 0, 0), "绿": (0, 200, 0), "蓝": (0, 0, 255),
    "黄": (255, 200, 0), "紫": (180, 0, 255), "青": (0, 220, 200),
    "粉": (255, 80, 160), "橙": (255, 120, 0), "白": (255, 255, 255),
}
ACTION_WORDS = {
    "站起来": "stand", "起身": "stand", "站立": "stand",
    "坐下": "sit", "坐": "sit",
    "趴下": "lie", "趴": "lie",
    "跳舞": "dance", "跳个舞": "dance",
    "前进": "walk", "往前走": "walk", "走两步": "walk",
    "后退": "back", "往后退": "back",
    "左转": "left", "右转": "right",
    "摇尾巴": "wag", "摇摇头": "shake", "摇头": "shake",
    "停下": "stop", "别动": "stop", "停": "stop",
}


def _device_cmd_from_text(text: str):
    """从文字里解析设备指令，返回 (kind, value, reply) 或 (None, None, None)。"""
    t = (text or "").strip()
    if not t or len(t) > 40:
        return None, None, None

    # ---------- 灯 ----------
    if any(k in t for k in ("灯", "灯珠", "发光")):
        if any(k in t for k in ("灯光秀", "彩虹", "彩灯", "跑马", "灯效")):
            return "led", "rainbow", "好，来一段彩虹灯光秀。"
        if "呼吸" in t:
            return "led", "breathing", "好，呼吸灯安排。"
        if "闪" in t:
            return "led", "blink", "好，闪给你看。"
        if "流水" in t:
            return "led", "chase", "好，流水灯走起。"
        if any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            return "led", "0,0,0", "好，灯关了。"
        for kw, rgb in LED_COLOR_MAP.items():
            if kw in t:
                return "led", f"{rgb[0]},{rgb[1]},{rgb[2]}", f"好，灯变成{kw}色了。"
        return "led", "255,200,0", "好，灯亮了。"

    # ---------- 动作 ----------
    for word, act in ACTION_WORDS.items():
        if word in t:
            return "action", act, f"好，{word}。"

    return None, None, None


def _push_device_cmd(kind: str, value: str) -> bool:
    """下发到设备心跳队列。"""
    try:
        devs = store.list_devices() or []
        devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
        if not devs:
            return False
        store.push_command(devs[0]["mac"], kind, value)
        store.add_log("system", f"指令 {kind}={value}")
        return True
    except Exception:
        return False

'''
    idx = c.find("@app.post(\"/api/hardware/devices/{device_id}/commands\")")
    if idx > 0:
        c = c[:idx] + helper.strip() + "\n\n\n" + c[idx:]
        CON.write_text(c, encoding="utf-8")
        ast.parse(c)
        print("控制台：已加文字解析器")

# ---------------- 控制台：chat 拦截 ----------------
if "设备指令直通" not in c:
    c = CON.read_text(encoding="utf-8")
    lines = c.split("\n")
    idx = None
    for i, ln in enumerate(lines):
        if '"/api/agents/{agent_id}/chat"' in ln:
            idx = i
            break
    fn = None
    for i in range(idx or 0, min((idx or 0) + 8, len(lines))):
        if lines[i].lstrip().startswith("def "):
            fn = i
            break

    insert_at = (fn or 0) + 1
    if insert_at < len(lines) and lines[insert_at].strip().startswith('"""'):
        if lines[insert_at].strip().count('"""') < 2:
            j = insert_at + 1
            while j < len(lines) and '"""' not in lines[j]:
                j += 1
            insert_at = j + 1
        else:
            insert_at += 1

    block = [
        "    # 设备指令直通：灯珠/动作走心跳队列，不经过模型",
        "    try:",
        "        _kind, _val, _say = _device_cmd_from_text(str((body or {}).get('text') or ''))",
        "        if _kind:",
        "            if _push_device_cmd(_kind, _val):",
        "                return {'reply': _say, 'model': 'device-cmd', 'session_id': (body or {}).get('session_id') or ''}",
        "            return {'reply': '设备现在没连上，等它连上我再试。', 'model': 'device-cmd', 'session_id': ''}",
        "    except Exception:",
        "        pass",
    ]
    lines[insert_at:insert_at] = block
    c = "\n".join(lines)
    CON.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("控制台：chat 已加设备指令拦截")

# ---------------- 语音服务：本地命令 ----------------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

if "_handle_device_cmd" not in v:
    fn = '''async def _handle_device_cmd(conn, text: str) -> bool:
    """灯珠 / 灯光秀 / 动作：转给控制台硬件接口（设备心跳执行）。"""
    import os as _os

    import httpx as _httpx

    t = (text or "").strip()
    if not t or len(t) > 40:
        return False

    base = _os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")
    token = ""

    LED_COLORS = {
        "红": "255,0,0", "绿": "0,200,0", "蓝": "0,0,255",
        "黄": "255,200,0", "紫": "180,0,255", "青": "0,220,200",
        "粉": "255,80,160", "橙": "255,120,0", "白": "255,255,255",
    }

    kind = value = say = None

    if any(k in t for k in ("灯", "灯珠", "发光")):
        if any(k in t for k in ("灯光秀", "彩虹", "彩灯", "跑马", "灯效")):
            kind, value, say = "led", "rainbow", "好，来一段彩虹灯光秀。"
        elif "呼吸" in t:
            kind, value, say = "led", "breathing", "好，呼吸灯安排。"
        elif "闪" in t:
            kind, value, say = "led", "blink", "好，闪给你看。"
        elif "流水" in t:
            kind, value, say = "led", "chase", "好，流水灯走起。"
        elif any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            kind, value, say = "led", "0,0,0", "好，灯关了。"
        else:
            for kw, val in LED_COLORS.items():
                if kw in t:
                    kind, value, say = "led", val, f"好，灯变成{kw}色了。"
                    break
            if kind is None:
                kind, value, say = "led", "255,200,0", "好，灯亮了。"

    if kind is None:
        actions = {
            "坐下": ("sit", "好，坐下。"), "坐": ("sit", "好，坐下。"),
            "趴下": ("lie", "好，趴下。"), "趴": ("lie", "好，趴下。"),
            "跳舞": ("dance", "好，跳舞给你看。"),
            "站起来": ("stand", "好，站起来。"), "起身": ("stand", "好，起身。"),
            "前进": ("walk", "好，往前走。"), "往前走": ("walk", "好，往前走。"),
            "后退": ("back", "好，往后退。"),
            "左转": ("left", "好，左转。"), "右转": ("right", "好，右转。"),
            "摇尾巴": ("wag", "好，摇尾巴。"),
            "摇摇头": ("shake", "好，摇摇头。"),
            "停下": ("stop", "好，停下。"),
        }
        for word, (act, line) in actions.items():
            if word in t:
                kind, value, say = "action", act, line
                break

    if kind is None:
        return False

    try:
        with _httpx.Client(timeout=10.0) as c:
            devs = c.get(base + "/api/hardware/devices",
                         headers={"X-Hardware-Token": token}).json().get("devices") or []
            if not devs:
                await _speak_ack(conn, "设备还没连上，等一下再试。")
                return True
            did = devs[0]["id"]
            c.post(f"{base}/api/hardware/devices/{did}/commands",
                   headers={"X-Hardware-Token": token},
                   json={"type": kind, "params": {"value": value}})
        await _speak_ack(conn, say)
        return True
    except Exception:
        return False


'''
    idx = v.find("async def _handle_music_cmd")
    if idx > 0:
        v = v[:idx] + fn + v[idx:]
        print("语音：已加 _handle_device_cmd")

    # 调用
    call_idx = None
    lines = v.split("\n")
    for i, ln in enumerate(lines):
        if "if await _handle_music_cmd(conn, text):" in ln:
            call_idx = i
            break
    if call_idx is not None:
        indent = " " * (len(lines[call_idx]) - len(lines[call_idx].lstrip()))
        lines.insert(call_idx, indent + "if await _handle_device_cmd(conn, text):")
        lines.insert(call_idx + 1, indent + "    return")
        v = "\n".join(lines)
        print("语音：已接入设备指令分发")

    V.write_text(v, encoding="utf-8")
    ast.parse(v)
    print("语音：语法 OK")
else:
    print("语音：已存在")
