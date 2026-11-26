import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
base = "http://127.0.0.1:8102"

print("health:", httpx.get(base + "/rest/health", timeout=10).json())

r = httpx.get(base + "/rest/search", params={"q": "周杰伦", "limit": 3}, timeout=25).json()
print("搜索命中:", r.get("count"))
for s in r.get("songs", []):
    print("  {} - {}  {}s".format(s["title"], s["artist"], s["duration_seconds"]))
    print("    ", s["preview_url"][:70])

m = httpx.get(base + "/rest/recommend", params={"mood": "睡前", "limit": 2}, timeout=25).json()
print("\n推荐（睡前）:", m.get("count"), "首")
for s in m.get("songs", []):
    print("  {} - {}".format(s["title"], s["artist"]))
