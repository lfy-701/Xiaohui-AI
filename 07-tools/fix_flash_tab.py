"""修正烧录页 tab 注册与参数名。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = P.read_text(encoding="utf-8")

BAD = "if (name === 'fw-flash' || name === 'fw') { setTimeout(flashLoadPorts, 100); }"
GOOD = "if (t === 'fw-flash' || t === 'fw') { setTimeout(flashLoadPorts, 100); }"
if BAD in t:
    t = t.replace(BAD, GOOD, 1)
    print("已修正参数名")

old = "['dash', 'config', 'devices', 'logs', 'memory', 'kb', 'fw', 'training', 'mcp', 'music']"
new = "['dash', 'config', 'devices', 'logs', 'memory', 'kb', 'fw', 'fw-flash', 'training', 'mcp', 'music']"
if old in t:
    t = t.replace(old, new, 1)
    print("已把 fw-flash 加入 tab 列表")
else:
    print("⚠ tab 列表未匹配")

P.write_text(t, encoding="utf-8")
print("校验:", GOOD in t, "| tab-fw-flash 存在:", "tab-fw-flash" in t)
