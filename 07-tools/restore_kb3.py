"""最终版还原：清理占位符，补全童话结尾。"""
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\kb-service\data\memory.db"
raw = open(DB, "rb").read().decode("utf-8", "replace")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

FOX_ENDING = (
    "一起走到图书馆。雨停后，阿橙发现自己的尾巴有点湿，"
    "小兔递给它一块手帕，小刺猬帮它把书晾好。阿橙笑着说："
    "“原来帮助别人，也会收到朋友的关心。”"
)


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
    return seg.replace("\r\n", "\n")


def tidy(text: str) -> str:
    # 去掉结尾的占位符、替代字符、残留 ID
    text = re.sub(r"[\{\}]+\s*$", "", text)
    text = re.sub(r"[^\u4e00-\u9fff。！？、；：“”‘’（）《》…\w\s#\-\.]+$", "", text)
    text = re.sub(r"\n?#{2,3}\s*[\d\-]+岁\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


c = httpx.Client(base_url="http://127.0.0.1", timeout=60)
c.post("/login", data={"password": "xiaohui2026"})

TITLES = ["成语故事：亡羊补牢", "寓言故事：两只蚂蚁搬种子", "童话故事：小狐狸的红雨伞"]
for d in c.get("/api/kb/docs").json().get("docs", []):
    if d["title"] in TITLES:
        c.delete("/api/kb/docs/" + d["id"])

for t in TITLES:
    body = tidy(extract(t))
    if not body:
        print(f"!! 未提取到 {t}")
        continue

    if "小狐狸" in t:
        # 补全被截断的结尾
        if body.rstrip().endswith("像一座绿色小棚子。三个朋友挤在"):
            body = body.rstrip() + FOX_ENDING
        elif "阿橙笑着说" not in body:
            body = body.rstrip().rstrip("三个朋友挤在") + FOX_ENDING

    text = body if body.lstrip().startswith("#") else body
    r = c.post("/api/kb/ingest_text", json={"title": t, "text": text}).json()
    print(f"{t} -> {r['chunks']} 切片 / {len(text)} 字")

print("\n最终知识库:")
for d in c.get("/api/kb/docs").json()["docs"]:
    print(f"  {d['title']}  ({d['chunks']} 切片)")
