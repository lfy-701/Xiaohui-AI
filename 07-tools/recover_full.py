"""提取被删文档的完整原文（含元数据字段）。"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
raw = open(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db",
           "rb").read().decode("utf-8", "replace")

TITLES = ["成语故事：亡羊补牢", "寓言故事：两只蚂蚁搬种子", "童话故事：小狐狸的红雨伞"]

for t in TITLES:
    # 找「--- <title>」这种带正文的段落起点
    m = re.search(r"-{1,3}\s*" + re.escape(t), raw)
    if not m:
        print(f"!! 没找到 {t}")
        continue
    seg = raw[m.start(): m.start() + 2000]
    # 截到明显的二进制噪声为止（连续控制字符）
    seg = re.split(r"[\x00-\x08\x0b\x0c\x0e-\x1f]{1,}", seg)[0]
    seg = seg.replace("\x00", "")
    seg = re.sub(r"[ \t]+", " ", seg)
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    print("=" * 72)
    print(seg.strip()[:1500])
    print()
