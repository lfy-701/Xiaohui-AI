import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")
c = httpx.Client(base_url="http://127.0.0.1", timeout=60)
c.post("/login", data={"password": "xiaohui2026"})

print("=== 本地曲库 ===")
d = c.get("/api/music/local").json()
print("目录:", d["dir"], "| 曲目:", d["count"])
for x in d["tracks"]:
    print("  {}  {} MB  {}".format(x["title"], x["size_mb"], x["url"]))

print("\n=== 整首播放（Range 请求）===")
if d["tracks"]:
    url = "http://127.0.0.1" + d["tracks"][0]["url"]
    r = c.get(url, headers={"Range": "bytes=0-1023"})
    print("  完整请求:", c.head(url).status_code,
          "| Range 请求:", r.status_code, len(r.content), "bytes",
          "| content-type:", r.headers.get("content-type"))

print("\n=== 语音播报 ===")
r2 = c.post("/api/music/announce", json={"text": "找到两首歌，第一首是测试音A4"})
print("  合成:", r2.status_code, r2.headers.get("content-type"), len(r2.content), "bytes")

print("\n=== 页面元素 ===")
h = c.get("/").text
for k in ["playerBar", "loadLocalMusic", "playerNext", "announceNow", "seek"]:
    print(f"  {k:<16} {'✓' if k in h else '✗'}")
