"""从 SQLite 文件里抢救被删除的文档文本。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db")
raw = DB.read_bytes()

# 用替换模式解码，避免个别字节报错
text = raw.decode("utf-8", errors="replace")

# 提取连续的「可读文本」块：中文、英文、数字、常见标点、换行
CHUNK = re.compile(r"[\u4e00-\u9fff\u3000-\u303fA-Za-z0-9\s，。！？、；：“”‘’（）《》…—\-\.\,\!\?\(\)]{80,}")

blocks = []
for m in CHUNK.finditer(text):
    s = m.group(0).strip()
    # 过滤掉纯二进制噪声
    han = len(re.findall(r"[\u4e00-\u9fff]", s))
    if han < 30:
        continue
    blocks.append(s)

# 去重（按内容指纹）
seen = set()
uniq = []
for b in blocks:
    key = b[:60]
    if key in seen:
        continue
    seen.add(key)
    uniq.append(b)

print(f"共找到 {len(uniq)} 个候选文本块\n")

KEYWORDS = ["亡羊补牢", "蚂蚁", "红雨伞"]
for kw in KEYWORDS:
    print("=" * 70)
    print(f"【{kw}】相关块")
    print("=" * 70)
    for i, b in enumerate(uniq):
        if kw in b:
            print(f"--- 块 {i}（{len(b)} 字）---")
            print(b[:1200])
            print()
