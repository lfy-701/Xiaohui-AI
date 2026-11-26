"""最终验证：控制台烧录页元素是否齐全。"""
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

h = httpx.Client(base_url="http://127.0.0.1:8080", timeout=25)
h.post("/login", data={"password": "xiaohui2026"})
p = h.get("/").text

checks = {
    "烧录面板": 'id="tab-fw-flash"' in p,
    "tab 已注册": "'fw-flash'" in p,
    "开始按钮": "flashStart" in p,
    "串口刷新": "flashLoadPorts" in p,
    "状态轮询": "flashPoll" in p,
    "入口按钮": "进入在线烧录" in p,
}
for k, v in checks.items():
    print(f"  {k}: " + ("OK" if v else "缺失"))
print("  页面大小:", round(len(p) / 1024, 1), "KB")
