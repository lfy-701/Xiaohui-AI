import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=30)
c.post("/login", data={"password": "xiaohui2026"})

for d in c.get("/api/kb/docs").json()["docs"]:
    ch = c.get(f"/api/kb/docs/{d['id']}/chunks").json()
    text = "\n".join(x["text"] for x in ch["chunks"])
    marks = [m for m in ["故事正文", "知识介绍", "3-5岁", "6-8岁", "9-12岁", "内容简介"] if m in text]
    print("=" * 66)
    print(f"{d['title']}  |  {len(text)} 字  |  含: {' / '.join(marks)}")
    print("结尾:", text[-70:].replace("\n", " "))
