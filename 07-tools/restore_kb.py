"""从 memory.db 还原三篇被删文档，并重新导入知识库。"""
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db"
raw = open(DB, "rb").read().decode("utf-8", "replace")

TITLES = ["成语故事：亡羊补牢", "寓言故事：两只蚂蚁搬种子", "童话故事：小狐狸的红雨伞"]
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def extract(title: str) -> str:
    # 找到 "# 标题" 的位置，再往前找最近的 "分类:"
    m = re.search(r"#\s*" + re.escape(title), raw)
    if not m:
        return ""
    start = raw.rfind("分类:", 0, m.start())
    if start < 0:
        return ""
    seg = raw[start:start + 4000]
    c = CTRL.search(seg)
    if c:
        seg = seg[: c.start()]
    seg = seg.replace("\r\n", "\n")
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    return seg.strip()


def clean_tail(text: str) -> str:
    # 去掉结尾可能残留的库内部标识（16 位十六进制串）
    text = re.sub(r"\s*[0-9a-f]{8,}-\d+\s*$", "", text)
    return text.strip()


c = httpx.Client(base_url="http://127.0.0.1", timeout=60)
c.post("/login", data={"password": "xiaohui2026"})

for t in TITLES:
    body = clean_tail(extract(t))
    if not body:
        print(f"!! 未提取到 {t}")
        continue
    print("=" * 70)
    print(f"标题: {t}")
    print(f"长度: {len(body)} 字")
    print("开头:", body[:60].replace("\n", " "))
    print("结尾:", body[-60:].replace("\n", " "))

    r = c.post("/api/kb/ingest_text", json={"title": t, "text": body})
    print("导入:", r.status_code, r.json() if r.status_code == 200 else r.text[:100])
