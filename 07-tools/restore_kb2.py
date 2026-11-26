"""最终还原：清理尾部占位符，重建三篇文档。"""
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db"
raw = open(DB, "rb").read().decode("utf-8", "replace")

TITLES = ["成语故事：亡羊补牢", "寓言故事：两只蚂蚁搬种子", "童话故事：小狐狸的红雨伞"]
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def extract(title: str) -> str:
    m = re.search(r"#\s*" + re.escape(title), raw)
    if not m:
        return ""
    start = raw.rfind("分类:", 0, m.start())
    if start < 0:
        return ""
    seg = raw[start:start + 3000]
    c = CTRL.search(seg)
    if c:
        seg = seg[: c.start()]
    seg = seg.replace("\r\n", "\n")
    # 去掉尾部空标题与占位符
    seg = re.sub(r"\n?#{2,3}\s*[\d\-]+岁\s*\{*\}*\s*$", "", seg)
    seg = re.sub(r"[\{\}]+\s*$", "", seg)
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    return seg.strip()


c = httpx.Client(base_url="http://127.0.0.1", timeout=60)
c.post("/login", data={"password": "xiaohui2026"})

# 先删掉刚才导入的残缺版
for d in c.get("/api/kb/docs").json().get("docs", []):
    if d["title"] in TITLES:
        c.delete("/api/kb/docs/" + d["id"])
        print("删除待重建:", d["title"])

for t in TITLES:
    body = extract(t)
    if not body:
        print(f"!! 未提取到 {t}")
        continue
    # 标题行补上，保证首行是标题
    text = f"# {t}\n\n{body}" if not body.startswith("#") else body
    r = c.post("/api/kb/ingest_text", json={"title": t, "text": text}).json()
    print(f"导入 {t} -> {r['chunks']} 切片 / {len(text)} 字")

print("\n当前知识库:")
for d in c.get("/api/kb/docs").json()["docs"]:
    print(f"  {d['title']}  ({d['chunks']} 切片)")
