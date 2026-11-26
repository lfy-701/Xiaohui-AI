"""控制台：接收 battery_mv / battery_pct 并在设备 API 返回。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CON = Path(r"D:\AI-Companion-shared\xiaohui-ai\console")

# ---------- db.py：加列 ----------
DB = CON / "app" / "db.py"
d = DB.read_text(encoding="utf-8")
if "battery_mv" not in d:
    helper = '''

def ensure_device_battery_columns() -> None:
    """老库自动补列，避免迁移脚本。"""
    with db() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(devices)")]
        if cols and "battery_mv" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN battery_mv INTEGER")
        if cols and "battery_pct" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN battery_pct INTEGER")
        if cols and "battery_at" not in cols:
            conn.execute("ALTER TABLE devices ADD COLUMN battery_at REAL")


def set_device_battery(mac: str, mv: int, pct: int) -> None:
    import time

    ensure_device_battery_columns()
    with db() as conn:
        conn.execute(
            "UPDATE devices SET battery_mv=?, battery_pct=?, battery_at=? WHERE mac=?",
            (mv, pct, time.time(), mac),
        )
'''
    d = d.rstrip() + helper
    DB.write_text(d, encoding="utf-8")
    print("db.py: 已加电池字段与函数")

# ---------- main.py：心跳解析 + 返回 ----------
M = CON / "app" / "main.py"
m = M.read_text(encoding="utf-8")

if "set_device_battery" not in m:
    # 心跳处理里解析
    anchor = "def api_device_heartbeat("
    idx = m.find(anchor)
    if idx > 0:
        # 找该函数体内第一行 body 赋值附近插入
        seg = m[idx: idx + 2500]
        target = "    mac"
        # 直接在函数开头插入解析（用 body 变量名兼容 pydantic/dict）
        inject = '''    # 记录电池电压（固件会带 battery_mv / battery_pct）
    try:
        _bmv = getattr(body, "battery_mv", None)
        _bpct = getattr(body, "battery_pct", None)
        if _bmv is None and isinstance(body, dict):
            _bmv = body.get("battery_mv")
            _bpct = body.get("battery_pct")
        if _bmv:
            store.set_device_battery(getattr(body, "mac", mac if 'mac' in dir() else ""),
                                     int(_bmv), int(_bpct or 0))
    except Exception:
        pass
'''
        m = m[:idx + len(anchor)] + "\n" + inject + m[idx + len(anchor):]
        M.write_text(m, encoding="utf-8")
        print("main.py: 心跳已解析电池")
    else:
        print("⚠ 未找到心跳函数")

ast.parse(M.read_text(encoding="utf-8"))
print("语法 OK")
