"""在控制台导航加入「大模型专区」入口（只加一个链接，不动逻辑）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\index.html")
t = P.read_text(encoding="utf-8")

if "大模型专区" in t:
    print("入口已存在")
    sys.exit(0)

anchor = '        <div class="tab" data-tab="music" onclick="switchTab(\'music\')">音乐</div>'
link = (
    '        <a class="tab" href="http://100.100.221.34:8013/" target="_blank" '
    'rel="noreferrer" style="text-decoration:none" '
    'title="大模型专区（DeepSeek 云端）">大模型专区</a>'
)

if anchor in t:
    t = t.replace(anchor, anchor + "\n" + link, 1)
    P.write_text(t, encoding="utf-8")
    print("已加入「大模型专区」入口")
else:
    print("⚠ 未匹配到音乐 tab")
    for i, ln in enumerate(t.split("\n")):
        if "data-tab" in ln and "switchTab" in ln:
            print(f"  L{i+1}: {ln.strip()[:90]}")
