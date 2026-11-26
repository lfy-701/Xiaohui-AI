"""从 modelscope 完整下载 SenseVoiceSmall 权重。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from modelscope import snapshot_download

target = Path("models/SenseVoiceSmall")
print("目标目录:", target.resolve())

path = snapshot_download("iic/SenseVoiceSmall", local_dir=str(target))
print("下载完成:", path)

total = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
print(f"总大小: {total/1048576:.1f} MB")
for f in sorted(Path(path).rglob("*")):
    if f.is_file() and f.stat().st_size > 1048576:
        print(f"  {f.name:<40} {f.stat().st_size/1048576:7.1f} MB")
