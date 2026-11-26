import json
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=30)
c.post("/login", data={"password": "xiaohui2026"})

out = []
for d in c.get("/api/kb/docs").json()["docs"]:
    ch = c.get(f"/api/kb/docs/{d['id']}/chunks").json()
    text = "\n".join(x["text"] for x in ch["chunks"])
    out.append({"title": d["title"], "text": text})

for d in out:
    print("=" * 70)
    print(d["title"], "|", len(d["text"]), "字")
    print(d["text"])

with open(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\tools\kb_dump.json", "w",
          encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n已保存 kb_dump.json")
