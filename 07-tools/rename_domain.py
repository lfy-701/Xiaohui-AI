"""把项目里所有 xiaohui 改成 xiaohui（域名、密码、规则名、注释）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace")
SKIP = (".venv", "models", ".mscache", "node_modules", ".home", ".hfhome")

changed = []
for f in WS.rglob("*"):
    if not f.is_file():
        continue
    if any(p in f.parts for p in SKIP):
        continue
    if f.suffix.lower() not in (".ps1", ".md", ".py", ".yaml", ".html", ".json", ".txt"):
        continue
    try:
        text = f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    if "xiaohui" not in text:
        continue
    n = text.count("xiaohui")
    f.write_text(text.replace("xiaohui", "xiaohui"), encoding="utf-8")
    changed.append((f.relative_to(WS), n))

print(f"修改 {len(changed)} 个文件：")
for p, n in sorted(changed, key=lambda x: -x[1]):
    print(f"  {n:3} 处  {p}")
