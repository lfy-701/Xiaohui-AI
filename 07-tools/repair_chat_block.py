"""重写 api_test_chat 开头这段被写坏的分支（日期/天气/设备指令/澄清）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
lines = P.read_text(encoding="utf-8").split("\n")

# 找到函数体开始（docstring 之后）
start = None
for i, ln in enumerate(lines):
    if 'def api_test_chat(' in ln:
        start = i + 1
        break
if start is None:
    print("⚠ 未找到函数")
    sys.exit(1)

# 跳过 docstring
while lines[start].strip().startswith('"""') or lines[start].strip() == "":
    start += 1

# 找到正常流程起点
end = None
for i in range(start, start + 80):
    if "_prepare_chat(agent_id, body)" in lines[i]:
        end = i
        break
if end is None:
    print("⚠ 未找到正常流程起点")
    sys.exit(1)

block = [
    "    # 1) 日期/星期直接算",
    "    try:",
    "        _date_reply = _date_answer(str(getattr(body, 'text', '') or ''))",
    "        if _date_reply:",
    "            return {'reply': _date_reply, 'model': 'date',",
    "                    'session_id': getattr(body, 'session_id', '') or ''}",
    "    except Exception:",
    "        pass",
    "",
    "    # 2) 天气直接查 Open-Meteo（避免模型编温度）",
    "    try:",
    "        _w_reply = _weather_answer(str(getattr(body, 'text', '') or ''))",
    "        if _w_reply:",
    "            return {'reply': _w_reply, 'model': 'weather',",
    "                    'session_id': getattr(body, 'session_id', '') or ''}",
    "    except Exception:",
    "        pass",
    "",
    "    # 3) 设备指令直通（灯珠/动作/澄清）",
    "    try:",
    "        _txt = str(getattr(body, 'text', '') or '')",
    "        _kind, _val, _say = _device_cmd_from_text(_txt)",
    "        if _kind:",
    "            if _push_device_cmd(_kind, _val):",
    "                return {'reply': _say, 'model': 'device-cmd',",
    "                        'session_id': getattr(body, 'session_id', '') or ''}",
    "            return {'reply': '设备现在没连上，等它连上我再试。',",
    "                    'model': 'device-cmd', 'session_id': ''}",
    "        if 1 <= len(_txt.strip()) <= 5 and not any(ch in _txt for ch in '?？吗呢啊'):",
    "            return {'reply': '我没太听清，你是想让我做动作还是开灯？可以说「站起来」或「红灯」。',",
    "                    'model': 'clarify', 'session_id': ''}",
    "    except Exception:",
    "        pass",
    "",
]

lines[start:end] = block
P.write_text("\n".join(lines), encoding="utf-8")
ast.parse(P.read_text(encoding="utf-8"))
print("已重写 chat 开头分支；语法 OK")
