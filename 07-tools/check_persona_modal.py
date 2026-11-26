import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://xiaohui.me", timeout=25)
c.post("/login", data={"password": "xiaohui2026"})
h = c.get("/").text

print("=== 弹层结构 ===")
for k in ['id="personaAddBox" class="modal"', 'style="display:none"',
          "personaPresetText", "commitPersonaAdd", "closePersonaAdd"]:
    print("  {:<32} {}".format(k, "OK" if k in h else "缺失"))

print("\n=== 是否还有内联块残留 ===")
print("  border:1px dashed #c9d4e0 :", "仍在" if "border:1px dashed #c9d4e0" in h else "已移除")

print("\n=== 角色介绍卡内顺序 ===")
i1 = h.index('id="personaPresets"')
i2 = h.index('id="f-persona"')
i3 = h.index('id="personaAddBox"')
print("  预设标签 < 编辑框:", i1 < i2)
print("  编辑框 < 弹层:", i2 < i3)
print("  两者之间是否夹着输入框:", "personaPresetText" in h[i1:i2])
