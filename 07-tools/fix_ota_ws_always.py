"""修复 OTA：始终下发 websocket 地址（不再依赖 WS_URL 环境变量）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

old = '''    else:
        if WS_URL:
            resp["websocket"] = {"url": _ws_url_for(request), "token": WS_TOKEN, "version": 1}
        else:
            store.add_log("system", "警告：已绑定设备但未配置 WS_URL，设备将无法对话")'''

new = '''    else:
        # 始终下发地址：由 _ws_url_for 依据设备访问时的 Host 生成，
        # 换网络也不需要改配置（之前未设 WS_URL 就漏发，设备重启后连不上）
        resp["websocket"] = {
            "url": _ws_url_for(request),
            "token": WS_TOKEN,
            "version": 1,
        }'''

if old in t:
    t = t.replace(old, new, 1)
    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("OTA：已改为始终下发 websocket")
else:
    print("⚠ 未匹配")
