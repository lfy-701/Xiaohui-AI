"""下载 libopus .conda 包，解出 opus.dll，复制到 voice-server 的 venv。"""
import io
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import zstandard

sys.stdout.reconfigure(encoding="utf-8")

DEST = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\.venv\Scripts")
WORK = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\tools\_opus")
WORK.mkdir(parents=True, exist_ok=True)

API = "https://api.anaconda.org/package/conda-forge/libopus/files"
with urllib.request.urlopen(API, timeout=40) as r:
    files = json.load(r)
win = [f for f in files if f.get("attrs", {}).get("subdir") == "win-64"]
win.sort(key=lambda f: f.get("upload_time", ""), reverse=True)
pkg = win[0]
print("选中:', pkg['basename']" if False else f"选中: {pkg['basename']}")

url = pkg["download_url"]
if url.startswith("//"):
    url = "https:" + url
cache = WORK / Path(pkg["basename"]).name
if not cache.exists():
    print("下载…")
    with urllib.request.urlopen(url, timeout=180) as r, open(cache, "wb") as f:
        shutil.copyfileobj(r, f)
print("大小: {:.1f} MB".format(cache.stat().st_size / 1048576))

# .conda = zip( pkg-*.tar.zst , info-*.tar.zst )
dll_bytes = None
with zipfile.ZipFile(cache) as z:
    for name in z.namelist():
        if not name.endswith(".tar.zst"):
            continue
        raw = z.read(name)
        data = zstandard.ZstdDecompressor().decompress(raw, max_output_size=200 * 1024 * 1024)
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for m in tf.getmembers():
                if m.name.lower().endswith("opus.dll"):
                    dll_bytes = tf.extractfile(m).read()
                    print("找到:", m.name, len(dll_bytes), "bytes")
                    break
        if dll_bytes:
            break

if not dll_bytes:
    print("包里没有 opus.dll，列出内容供排查：")
    with zipfile.ZipFile(cache) as z:
        for name in z.namelist():
            if name.endswith(".tar.zst"):
                raw = z.read(name)
                data = zstandard.ZstdDecompressor().decompress(raw, max_output_size=200 * 1024 * 1024)
                with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                    for m in tf.getmembers()[:40]:
                        print("   ", m.name)
    sys.exit(1)

out = DEST / "opus.dll"
out.write_bytes(dll_bytes)
print("已写入:", out, out.stat().st_size, "bytes")
