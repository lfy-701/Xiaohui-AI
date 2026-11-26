import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

try:
    r = httpx.get(
        "https://gitee.com/api/v5/search/repositories",
        params={"q": "xiaozhi-esp32-server", "per_page": 20, "sort": "stars_count"},
        timeout=25,
    )
    data = r.json()
    print("结果数:", len(data))
    for d in data[:12]:
        name = d.get("full_name", "")
        stars = d.get("stargazers_count", 0)
        upd = (d.get("updated_at") or "")[:10]
        desc = (d.get("description") or "")[:60]
        print(f"  {name:<48} ★{stars:<6} {upd}")
        print(f"     {desc}")
except Exception as e:
    print("搜索失败:", type(e).__name__, str(e)[:200])
