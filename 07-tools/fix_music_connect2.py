"""放歌前确保设备已连接（设备每轮结束会断开）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "_wait_device_online" in t:
    print("已存在")
    sys.exit(0)

# 1) 加一个通用等待函数（放在文件末尾）
helper = '''

def _wait_device_online(timeout: float = 12.0) -> bool:
    """确保语音服务上有在线设备；没有就下发 connect 并等待。"""
    import time as _t

    def _count() -> int:
        try:
            with httpx.Client(timeout=8.0) as c:
                return int(c.get(f"{VOICE_HTTP_BASE}/api/console/status").json().get("count") or 0)
        except Exception:
            return 0

    if _count() > 0:
        return True
    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: d.get("last_seen") or 0, reverse=True)
    if not devs:
        return False
    try:
        store.push_command(devs[0]["mac"], "connect", "1")
    except Exception:
        pass
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        _t.sleep(0.8)
        if _count() > 0:
            return True
    return False
'''

t = t.rstrip() + helper

# 2) 放歌接口里调用
old = '''    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()'''

new = '''    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    # 设备每轮对话结束会断开，放歌前先确保在线
    if not _wait_device_online(12.0):
        return {"ok": False, "error": "设备未在线，请先唤醒设备"}

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
