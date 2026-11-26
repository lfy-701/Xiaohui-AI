"""让 OTA 下发的 websocket 地址跟随设备实际访问到的地址，换网也不怕。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\console\app\main.py")
t = F.read_text(encoding="utf-8")

if "_ws_url_for" in t:
    print("已存在，跳过")
    sys.exit(0)

# 1) 新增生成函数（放在 /ota/ 之前）
anchor = '@app.post("/ota/")'
helper = '''def _ws_url_for(request: Request) -> str:
    """按设备实际访问到的地址生成 websocket 地址。

    设备从哪个 IP 访问到控制台，就下发哪个 IP 的语音服务地址，
    这样电脑换网络（热点 / 校园网 / 有线）后不需要改配置。
    """
    from urllib.parse import urlparse

    cfg = WS_URL or "ws://127.0.0.1:8000/xiaozhi/v1/"
    try:
        p = urlparse(cfg)
        port = p.port or 8000
        path = p.path or "/xiaozhi/v1/"
    except Exception:
        port, path = 8000, "/xiaozhi/v1/"

    host = (request.headers.get("host") or "").split(":")[0].strip()
    if not host:
        host = request.client.host if request.client else "127.0.0.1"
    return f"ws://{host}:{port}{path}"


@app.post("/ota/")'''
if anchor in t:
    t = t.replace(anchor, helper, 1)
    print("已加入 _ws_url_for")
else:
    print("⚠ /ota/ 锚点未匹配")

# 2) OTA 里改用动态地址
old = '            resp["websocket"] = {"url": WS_URL, "token": WS_TOKEN, "version": 1}'
new = '            resp["websocket"] = {"url": _ws_url_for(request), "token": WS_TOKEN, "version": 1}'
if old in t:
    t = t.replace(old, new, 1)
    print("OTA 已改为动态 websocket 地址")
else:
    print("⚠ websocket 赋值锚点未匹配")

F.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("语法 OK")
for k in ["_ws_url_for", "_ws_url_for(request)"]:
    print("  {:<20} {}".format(k, "OK" if k in t else "缺失"))
