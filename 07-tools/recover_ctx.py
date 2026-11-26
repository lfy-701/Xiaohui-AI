"""打印每个标题附近的原始上下文，看清文档真实结构。"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
raw = open(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db",
           "rb").read().decode("utf-8", "replace")

TITLES = ["成语故事：亡羊补牢", "寓言故事：两只蚂蚁搬种子", "童话故事：小狐狸的红雨伞"]

for t in TITLES:
    print("=" * 72)
    print("标题:", t)
    for m in re.finditer(re.escape(t), raw):
        ctx = raw[max(0, m.start() - 80): m.start() + 700]
        ctx = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "·", ctx)
        if "故事正文" in ctx:
            print("---- 上下文 ----")
            print(ctx.replace("·" * 3, "·")[:800])
            print()
            break
