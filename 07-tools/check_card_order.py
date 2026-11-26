import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

c = httpx.Client(base_url="http://xiaohui.me", timeout=25)
c.post("/login", data={"password": "xiaohui2026"})
h = c.get("/").text

i_basic = h.index("<h4>基本</h4>")
i_voice = h.index("<h4>角色音色</h4>")
i_persona = h.index(">角色介绍<")

print("=== 角色页卡片顺序 ===")
print("  基本    位置:", i_basic)
print("  角色音色 位置:", i_voice)
print("  角色介绍 位置:", i_persona)
print("  顺序正确:", i_basic < i_voice < i_persona)

print("\n=== 关键控件是否都在 ===")
for k in ["f-name", "f-wake", "f-voice-group", "f-voice", "previewVoice", "personaPresets", "f-persona"]:
    print("  {:<18} {}".format(k, "OK" if k in h else "缺失"))

print("\n=== 结构完整性 ===")
seg = h[i_basic - 200:i_persona + 200]
print("  cfg-card 开:", seg.count('class="cfg-card"'), "闭(附近):", seg.count("</div>"))
