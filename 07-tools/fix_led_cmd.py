"""修正灯珠命令：用颜色名 + 支持灯光秀（led_effect）。"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
t = F.read_text(encoding="utf-8")

start = t.find("async def _handle_local_cmd(conn, text: str) -> bool:")
end = t.find("async def _handle_music_cmd(conn, text: str) -> bool:")
if start < 0 or end < 0:
    print("⚠ 未找到函数边界")
    sys.exit(1)

new = '''async def _handle_local_cmd(conn, text: str) -> bool:
    """灯珠 / 灯效 / 笑话 的本地直通命令（不经过模型）。"""
    import json as _json
    import random as _random

    t = (text or "").strip()
    if not t:
        return False

    from core.providers.tools.device_mcp import call_mcp_tool

    async def _mcp(name, args):
        try:
            await call_mcp_tool(conn, conn.mcp_client, name,
                                _json.dumps(args, ensure_ascii=False), timeout=5)
            return True
        except Exception:
            return False

    # ---------- 灯光秀 ----------
    if any(k in t for k in ("灯光秀", "灯效", "彩虹灯", "彩灯", "闪一下", "跑马灯", "呼吸灯")):
        if "呼吸" in t:
            effect = "breathing"
        elif "闪" in t:
            effect = "blink"
        elif "流水" in t or "跑马" in t:
            effect = "chase"
        else:
            effect = "rainbow"
        if await _mcp("self.led_effect", {"effect": effect}):
            names = {"rainbow": "彩虹灯光秀", "breathing": "呼吸灯",
                     "blink": "闪烁灯", "chase": "流水灯"}
            await _speak_ack(conn, f"好，来一段{names.get(effect, '灯光秀')}。")
            return True
        return False

    # ---------- 灯珠颜色 ----------
    colors = {
        "红": "red", "绿": "green", "蓝": "blue", "黄": "yellow",
        "青": "cyan", "紫": "purple", "粉": "pink", "橙": "orange",
        "白": "white", "暖": "warm",
    }
    if any(k in t for k in ("灯", "灯珠", "发光", "亮")):
        if any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            if await _mcp("self.set_led", {"color": "off"}):
                await _speak_ack(conn, "好，灯关了。")
                return True
            return False
        for kw, name in colors.items():
            if kw in t:
                if await _mcp("self.set_led", {"color": name}):
                    await _speak_ack(conn, f"好，灯变成{kw}色了。")
                    return True
                return False
        if await _mcp("self.set_led", {"color": "warm"}):
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

t = t[:start] + new + t[end:]
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("灯珠命令已修正（颜色名）+ 灯光秀已加入；语法 OK")
