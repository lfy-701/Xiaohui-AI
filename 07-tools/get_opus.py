"""从 conda-forge 下载 libopus 包，提取 opus.dll 到 venv。"""
import io
import json
import sys
import tarfile
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API = "https://api.anaconda.org/package/conda-forge/libopus/files"
try:
    with urllib.request.urlopen(API, timeout=40) as r:
        files = json.load(r)
except Exception as e:
    print("查询失败:", e)
    sys.exit(1)

win = [f for f in files if f.get("attrs", {}).get("subdir") == "win-64"]
print("win-64 包数:", len(win))
win.sort(key=lambda f: f.get("upload_time", ""), reverse=True)

for f in win[:6]:
    print("  ", f["basename"], f.get("attrs", {}).get("subdir"), f.get("upload_time", "")[:10])
