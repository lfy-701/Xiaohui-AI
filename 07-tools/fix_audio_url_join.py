"""修正 AUDIO_CACHE_BASE 拼接：避免 /audio/audio 双路径。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

old = '''    _cache_base = os.getenv("AUDIO_CACHE_BASE", "http://<你的服务器局域网IP>:8106")
    if _cache_base:
        import urllib.parse as _up
        url = _cache_base.rstrip("/") + "/audio?src=" + _up.quote(url, safe="")'''

new = '''    _cache_base = os.getenv("AUDIO_CACHE_BASE", "http://<你的服务器局域网IP>:8080/audio").rstrip("/")
    if _cache_base:
        import urllib.parse as _up
        # 基地址可能已经带 /audio，避免拼成 /audio/audio
        _sep = "?src=" if _cache_base.endswith("/audio") else "/audio?src="
        url = _cache_base + _sep + _up.quote(url, safe="")'''

count = t.count(old)
if count:
    t = t.replace(old, new)
    M.write_text(t, encoding="utf-8")
    ast.parse(t)
    print(f"已修正 {count} 处拼接；语法 OK")
else:
    print("⚠ 未匹配拼接代码")
