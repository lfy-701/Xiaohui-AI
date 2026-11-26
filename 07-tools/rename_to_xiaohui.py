"""把控制台里所有「小小」改成「小慧」，品牌名改成小慧控制台。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace")

FILES = [
    WS / "console" / "app" / "main.py",
    WS / "console" / "app" / "auth.py",
    WS / "console" / "static" / "index.html",
    WS / "voice-server" / "main" / "xiaozhi-server" / "data" / ".config.yaml",
    WS / "start-console.ps1",
]

# 顺序很重要：先换长串，再换短串
REPLACERS = [
    ("小小 · 智能体控制台", "小慧 · 智能体控制台"),
    ("标题，例如：小小使用说明", "标题，例如：小慧使用说明"),
    ("你好，我是小小，很高兴认识你。", "你好，我是小慧，很高兴认识你。"),
    ("こんにちは、小小です。", "こんにちは、小慧です。"),
    ("你叫小小", "你叫小慧"),
    ("已创建默认智能体：小小", "已创建默认智能体：小慧"),
    ("绑定「小小」", "绑定「小慧」"),
    ('"name": "小小"', '"name": "小慧"'),
    ("小小", "小慧"),
]

for f in FILES:
    if not f.exists():
        print(f"跳过（不存在）: {f.name}")
        continue
    text = f.read_text(encoding="utf-8")
    before = text
    for a, b in REPLACERS:
        text = text.replace(a, b)
    if text != before:
        f.write_text(text, encoding="utf-8")
        n = sum(before.count(a) for a, _ in REPLACERS if a in before)
        print(f"已修改: {f.relative_to(WS)}")
    else:
        print(f"无变化: {f.relative_to(WS)}")
