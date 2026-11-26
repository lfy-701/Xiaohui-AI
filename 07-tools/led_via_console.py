"""灯珠/灯光秀统一走心跳队列（网页已验证可用）。

1) 控制台：/api/device/led 对本机放行（语音服务调用）
2) 控制台：打字对话里识别灯珠/灯效关键词 → 直接下发并返回话术
3) 语音服务：本地命令改为调控制台接口
"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CON = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = CON.read_text(encoding="utf-8")

# ---------- 1) 中间件放行 ----------
if 'path.startswith("/api/device/led")' not in c:
    old = '''    # 设备拉音频不需要登录（纯转发，无敏感数据）
    if path.startswith("/audio"):
        return await call_next(request)'''
    new = '''    # 设备拉音频不需要登录（纯转发，无敏感数据）
    if path.startswith("/audio"):
        return await call_next(request)
    # 本机语音服务下发灯珠命令
    if path.startswith("/api/device/led"):
        try:
            if request.client and request.client.host in ("127.0.0.1", "::1"):
                return await call_next(request)
        except Exception:
            pass'''
    if old in c:
        c = c.replace(old, new, 1)
        print("中间件：已放行 /api/device/led（本机）")

# ---------- 2) 打字对话拦截灯珠 ----------
if "def _led_command_from_text" not in c:
    helper = '''

LED_COLORS = {
    "红": (255, 0, 0), "绿": (0, 200, 0), "蓝": (0, 0, 255),
    "黄": (255, 200, 0), "紫": (180, 0, 255), "青": (0, 220, 200),
    "粉": (255, 80, 160), "橙": (255, 120, 0), "白": (255, 255, 255),
}


def _led_command_from_text(text: str):
    """从文字里解析灯珠/灯效命令，返回 (value, 回复话术) 或 (None, None)。"""
    t = (text or "").strip()
    if not t:
        return None, None
    if not any(k in t for k in ("灯", "灯珠", "发光")):
        return None, None

    if any(k in t for k in ("灯光秀", "彩虹", "灯效", "彩灯", "跑马")):
        return "rainbow", "好，来一段彩虹灯光秀。"
    if "呼吸" in t:
        return "breathing", "好，呼吸灯安排。"
    if "闪" in t:
        return "blink", "好，闪给你看。"
    if "流水" in t:
        return "chase", "好，流水灯走起。"
    if any(k in t for k in ("关", "灭", "不要亮", "别亮")):
        return "0,0,0", "好，灯关了。"
    for kw, rgb in LED_COLORS.items():
        if kw in t:
            return f"{rgb[0]},{rgb[1]},{rgb[2]}", f"好，灯变成{kw}色了。"
    return "255,200,0", "好，灯亮了。"

'''
    idx = c.find("@app.post(\"/api/device/led\")")
    if idx > 0:
        c = c[:idx] + helper.strip() + "\n\n\n" + c[idx:]
        print("控制台：已加灯珠文字解析")

CON.write_text(c, encoding="utf-8")
ast.parse(c)

# ---------- 3) 语音服务：本地命令改走控制台 ----------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

start = v.find("async def _handle_local_cmd(conn, text: str) -> bool:")
end = v.find("async def _handle_music_cmd(conn, text: str) -> bool:")

new_fn = '''async def _handle_local_cmd(conn, text: str) -> bool:
    """灯珠 / 灯效 / 笑话：走控制台心跳队列（已验证可用）。"""
    import os as _os
    import random as _random

    import httpx as _httpx

    t = (text or "").strip()
    if not t:
        return False

    base = _os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")

    def _push(value: str) -> bool:
        try:
            with _httpx.Client(timeout=8.0) as c:
                r = c.post(base + "/api/device/led", json={"value": value})
                return r.status_code < 400
        except Exception:
            return False

    # ---------- 灯光秀 ----------
    if any(k in t for k in ("灯光秀", "灯效", "彩虹灯", "彩灯", "跑马灯", "呼吸灯", "闪一下", "流水灯")):
        if "呼吸" in t:
            effect, say = "breathing", "好，呼吸灯安排。"
        elif "闪" in t:
            effect, say = "blink", "好，闪给你看。"
        elif "流水" in t or "跑马" in t:
            effect, say = "chase", "好，流水灯走起。"
        else:
            effect, say = "rainbow", "好，来一段彩虹灯光秀。"
        if _push(effect):
            await _speak_ack(conn, say)
            return True
        return False

    # ---------- 灯珠颜色 ----------
    colors = {
        "红": (255, 0, 0), "绿": (0, 200, 0), "蓝": (0, 0, 255),
        "黄": (255, 200, 0), "紫": (180, 0, 255), "青": (0, 220, 200),
        "粉": (255, 80, 160), "橙": (255, 120, 0), "白": (255, 255, 255),
    }
    if any(k in t for k in ("灯", "灯珠", "发光", "亮")):
        if any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            if _push("0,0,0"):
                await _speak_ack(conn, "好，灯关了。")
                return True
            return False
        for kw, rgb in colors.items():
            if kw in t:
                if _push(f"{rgb[0]},{rgb[1]},{rgb[2]}"):
                    await _speak_ack(conn, f"好，灯变成{kw}色了。")
                    return True
                return False
        if _push("255,200,0"):
            await _speak_ack(conn, "好，灯亮了。")
            return True
        return False

    # ---------- 笑话 ----------
    if any(k in t for k in ("笑话", "逗我", "讲个好笑")):
        jokes = [
            "有一天，小明问爸爸：为什么手机要充电？爸爸说：因为它也要吃饭呀。",
            "小狗为什么不上网？因为它怕网住自己。",
            "什么东西越洗越脏？水。",
            "小兔子为什么不用火柴？因为它有兔毛。",
            "老师问：谁最会游泳？同学说：鱼。老师说：对，因为它是老司机。",
        ]
        await _speak_ack(conn, _random.choice(jokes))
        return True

    return False


'''

if start > 0 and end > start:
    v = v[:start] + new_fn + v[end:]
    V.write_text(v, encoding="utf-8")
    ast.parse(v)
    print("语音服务：灯珠命令已改为走控制台队列")
