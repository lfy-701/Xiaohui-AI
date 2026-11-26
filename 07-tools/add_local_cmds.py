"""本地直通命令：笑话 + 灯珠控制（不经过模型，快且稳）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
lines = F.read_text(encoding="utf-8").split("\n")

if "_handle_local_cmd" in lines and any("_handle_local_cmd" in x for x in lines):
    # 已有函数，只需确认调用存在
    pass

# 1) 插入处理函数（放在 _handle_music_cmd 之前）
func = '''async def _handle_local_cmd(conn, text: str) -> bool:
    """笑话 / 灯珠 / 灯光的本地直通命令。"""
    import json as _json
    import random as _random

    t = (text or "").strip()
    if not t:
        return False

    # ---------- 灯珠 ----------
    color_words = {
        "红": (255, 0, 0), "绿": (0, 255, 0), "蓝": (0, 120, 255),
        "黄": (255, 200, 0), "紫": (160, 0, 255), "青": (0, 220, 200),
        "橙": (255, 120, 0), "粉": (255, 80, 160), "白": (255, 255, 255),
        "灭": (0, 0, 0), "关灯": (0, 0, 0), "关掉灯": (0, 0, 0),
    }
    if any(k in t for k in ("灯", "灯珠", "发光")):
        rgb = None
        for k, v in color_words.items():
            if k in t:
                rgb = v
                break
        if rgb is None:
            rgb = (255, 200, 0)      # 没说颜色就亮暖黄
        try:
            from core.providers.tools.device_mcp import call_mcp_tool

            await call_mcp_tool(
                conn, conn.mcp_client, "self.set_led",
                _json.dumps({"r": rgb[0], "g": rgb[1], "b": rgb[2]}),
                timeout=5,
            )
            name = next((k for k, v in color_words.items() if v == rgb), "亮")
            await _speak_ack(conn, f"好，灯{('关了' if rgb == (0, 0, 0) else '变' + name + '色了')}")
            return True
        except Exception:
            return False

    # ---------- 笑话 ----------
    if any(k in t for k in ("笑话", "讲个笑话", "逗我")):
        jokes = [
            "有一天，小明问爸爸：为什么手机要充电？爸爸说：因为它也要吃饭呀。",
            "小狗为什么不上网？因为它怕网住自己。",
            "什么东西越洗越脏？水。",
            "小兔子为什么不用火柴？因为它有兔毛。",
            "老师问：谁最会游泳？同学说：鱼。老师说：对，因为它是老司机。",
        ]
        try:
            await _speak_ack(conn, _random.choice(jokes))
            return True
        except Exception:
            return False

    return False


'''

idx = None
for i, ln in enumerate(lines):
    if ln.startswith("async def _handle_music_cmd"):
        idx = i
        break

if idx is None:
    print("⚠ 未找到插入点")
    sys.exit(1)

if not any("async def _handle_local_cmd" in x for x in lines):
    lines[idx:idx] = func.split("\n")
    print("已插入 _handle_local_cmd")

# 2) 在音乐命令之前调用
call_idx = None
for i, ln in enumerate(lines):
    if "if await _handle_music_cmd(conn, text):" in ln:
        call_idx = i
        break

if call_idx is not None:
    indent = " " * (len(lines[call_idx]) - len(lines[call_idx].lstrip()))
    if "await _handle_local_cmd(conn, text)" not in "\n".join(lines):
        lines.insert(call_idx, indent + "if await _handle_local_cmd(conn, text):")
        lines.insert(call_idx + 1, indent + "    return")
        print("已接入本地命令分发")

F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("语法 OK")
