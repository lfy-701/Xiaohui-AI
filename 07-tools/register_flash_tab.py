"""把 fw-flash 注册进 switchTab 的 tab 列表。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = P.read_text(encoding="utf-8")

m = re.search(r"(\[[^\]]*'fw'[^\]]*\])\.forEach\(k =>", t)
if not m:
    print("⚠ 未找到 tab 列表")
    sys.exit(1)

arr = m.group(1)
if "'fw-flash'" in arr:
    print("已注册，无需重复")
    sys.exit(0)

new_arr = arr.replace("'fw'", "'fw', 'fw-flash'", 1)
t = t[:m.start(1)] + new_arr + t[m.end(1):]
P.write_text(t, encoding="utf-8")
print("已注册 fw-flash:", new_arr[:90])
