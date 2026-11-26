import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://xiaohui.me", timeout=25)
c.post("/login", data={"password": "xiaohui2026"})
h = c.get("/").text

print("=== 导航 ===")
for tab in ["概览", "配置", "设备", "日志", "记忆", "知识库", "固件", "MCP 工具", "音乐"]:
    print("  {:<8} {}".format(tab, "OK" if ">" + tab + "</div>" in h else "缺失"))

print("\n=== 配置页元素 ===")
for k in ["cfg-tabs", "cfg-role", "cfg-model", "cfg-voice",
          "chip-add", "personaAddBox", "personaPresetText", "commitPersonaAdd",
          "renderPersonaPresets", "onPersonaInput", "personaCount", "cfg-actions"]:
    print("  {:<22} {}".format(k, "OK" if k in h else "缺失"))

print("\n=== 残留检查 ===")
for k in ["togglePersonaCustom", "f-persona-custom", "设定</div>"]:
    print("  {:<22} {}".format(k, "仍存在(!)" if k in h else "已清理"))

m = re.search(r"<script>(.*?)</script>", h, re.S)
js = m.group(1) if m else ""
print("\n=== JS 括号 ===")
for a, b in [("{", "}"), ("(", ")"), ("[", "]")]:
    print("  {}{} 差 {}".format(a, b, js.count(a) - js.count(b)))
