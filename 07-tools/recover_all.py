"""把每篇文档的所有切片片段都找出来，拼接成完整原文。"""
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db"
raw = open(DB, "rb").read().decode("utf-8", "replace")

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
BLOCK = re.compile(r"[\u4e00-\u9fff\u3000-\u303fA-Za-z0-9\s，。！？、；：“”‘’（）《》…—\-\.\,\!\?\(\)\#\{\}]{60,}")

# 每篇文档的识别特征（标题 + 独有关键词）
DOCS = {
    "成语故事：亡羊补牢": ["羊圈", "亡羊补牢", "补牢"],
    "寓言故事：两只蚂蚁搬种子": ["蚂蚁", "滚木", "种子"],
    "童话故事：小狐狸的红雨伞": ["阿橙", "红雨伞", "刺猬"],
}

blocks = []
for m in BLOCK.finditer(raw):
    s = m.group(0)
    if len(re.findall(r"[\u4e00-\u9fff]", s)) < 20:
        continue
    blocks.append(s.strip())

print(f"候选块: {len(blocks)}\n")

for title, keys in DOCS.items():
    mine = [b for b in blocks if any(k in b for k in keys)]
    # 去重
    seen, uniq = set(), []
    for b in mine:
        fp = b[:50]
        if fp in seen:
            continue
        seen.add(fp)
        uniq.append(b)
    print("=" * 70)
    print(f"{title}：{len(uniq)} 个相关块")
    for i, b in enumerate(uniq):
        head = b[:40].replace("\n", " ")
        tail = b[-40:].replace("\n", " ")
        print(f"  [{i}] {len(b):4} 字 | {head} ... {tail}")
