import httpx
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=60)
c.post("/login", data={"password": "xiaohui2026"})

d = c.get("/api/voices").json()
print("来源:", d["source"], "| 总数:", d["total"])
print("\n分组：")
for g in d["groups"]:
    print(f"  {g['name']:<12} {g['count']}")

print("\n中文全部：")
for v in d["voices"]:
    if v["group"].startswith("中文"):
        print("  {:<34} {}".format(v["id"], v["label"]))

print("\n外语抽样：")
seen = set()
for v in d["voices"]:
    if v["group"] in ("英语", "日语", "韩语", "法语", "德语") and v["group"] not in seen:
        seen.add(v["group"])
        print("  {:<30} {}".format(v["id"], v["label"]))
