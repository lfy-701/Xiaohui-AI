"""把剩余的品牌名统一成「小慧控制台」。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace")
SKIP = (".venv", "models", ".mscache", "node_modules", ".home", ".hfhome")

# 长串优先
REPLACERS = [
    ("小慧控制台", "小慧控制台"),
    ("小慧知识库与记忆", "小慧知识库与记忆"),
    ("小慧控制台", "小慧控制台"),
    ("# 小慧 —— 知识库 & 记忆服务", "# 小慧 —— 知识库 & 记忆服务"),
    ("小慧", "小慧"),
    ("小慧的知识库", "小慧的知识库"),
    ("小慧", "小慧"),
    ("小慧", "小慧"),
]

changed = []
for f in WS.rglob("*"):
    if not f.is_file() or any(p in f.parts for p in SKIP):
        continue
    if f.suffix.lower() not in (".ps1", ".md", ".py", ".yaml", ".html", ".json", ".txt"):
        continue
    if "voice-server" in str(f) and "xiaozhi-server" in str(f):
        # 上游仓库不动
        continue
    try:
        text = f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    before = text
    for a, b in REPLACERS:
        text = text.replace(a, b)
    if text != before:
        f.write_text(text, encoding="utf-8")
        changed.append(f.relative_to(WS))

print(f"修改 {len(changed)} 个文件：")
for p in sorted(changed):
    print("  ", p)
