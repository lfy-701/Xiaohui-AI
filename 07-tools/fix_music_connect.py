"""放歌：先确保设备连接，再推流（设备每轮结束会断开）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "确保设备连接" in t:
    print("已存在")
    sys.exit(0)

old = '''    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()'''

new = '''    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    # 确保设备连接：设备每轮对话结束会断开，先唤醒再推流
    import time as _t

    def _online() -> bool:
        try:
            with httpx.Client(timeout=8.0) as _c:
                r = _c.post(f"{VOICE_HTTP_BASE}/api/console/play",
                            json={"url": url, "probe_only": True})
                return r.status_code == 200
        except Exception:
            return False

    devs0 = store.list_devices() or []
    if devs0:
        try:
            store.push_command(devs0[0]["mac"], "connect", "1")
        except Exception:
            pass
        deadline = _t.time() + 10
        while _t.time() < deadline:
            _t.sleep(0.8)
            try:
                with httpx.Client(timeout=8.0) as _c:
                    st = _c.post("http://127.0.0.1:8003/api/console/say",
                                 json={"text": ""}).json()
            except Exception:
                st = {}
            if st.get("error") and "不在线" not in str(st.get("error")):
                break

    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()'''

if old in t:
    t = t.replace(old, new, 1)
    M.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已加连接保障")
else:
    print("⚠ 未匹配放歌接口")
