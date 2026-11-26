import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=60)
c.post("/login", data={"password": "xiaohui2026"})
h = c.get("/").text

print("=== 品牌检查 ===")
print("  标题        :", "小慧控制台" in h)
print("  logo        :", "小慧<span>控制台</span>" in h)
print("  副标题      :", "智能体 · 知识库 · 记忆" in h)
print("  残留小小    :", h.count("小小"), "处")
print("  残留 xiaohui:", h.count("xiaohui"), "处")

print("\n=== 人设预设开头 ===")
for m in re.findall(r"你叫([^，,]{1,4})[，,]", h):
    print("  ", m)

print("\n=== 试听 ===")
r = c.get("/api/voices/zh-CN-XiaoxiaoNeural/sample")
print("  合成:", r.status_code, len(r.content), "bytes")
