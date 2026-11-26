"""动作编辑器后端：自定义动作 CRUD + pose/led 下发。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\db.py")
M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")

# ---------------- db.py ----------------
d = DB.read_text(encoding="utf-8")
if "custom_actions" not in d:
    d = d.rstrip() + '''


def init_actions_table() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                angles TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )


def list_actions() -> list:
    import time

    init_actions_table()
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, angles, created_at FROM custom_actions ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def add_action(name: str, angles: str) -> int:
    import time

    init_actions_table()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO custom_actions (name, angles, created_at) VALUES (?,?,?)",
            (name.strip() or "未命名", angles, time.time()),
        )
        return int(cur.lastrowid)


def delete_action(aid: int) -> None:
    init_actions_table()
    with db() as conn:
        conn.execute("DELETE FROM custom_actions WHERE id=?", (aid,))
'''
    DB.write_text(d, encoding="utf-8")
    print("db.py: 已加 custom_actions")
else:
    print("db.py: 已存在")

# ---------------- main.py ----------------
m = M.read_text(encoding="utf-8")
if "/api/actions" not in m:
    m = m.rstrip() + '''


# ---------------------------------------------------------------- 动作编辑

class ActionIn(BaseModel):
    name: str = ""
    angles: str = "90,90,90,90"


@app.get("/api/actions")
def api_actions_list():
    return {"actions": store.list_actions()}


@app.post("/api/actions")
def api_actions_add(body: ActionIn):
    aid = store.add_action(body.name, body.angles)
    store.add_log("system", f"保存动作：{body.name} ({body.angles})")
    return {"ok": True, "id": aid}


@app.delete("/api/actions/{aid}")
def api_actions_delete(aid: int):
    store.delete_action(aid)
    return {"ok": True}


@app.post("/api/device/pose")
def api_device_pose(body: ActionIn):
    """下发一组舵机角度（4 个 + 头部/尾部补 90）。"""
    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
    if not devs:
        raise HTTPException(404, "没有绑定设备")
    parts = [p.strip() for p in body.angles.split(",") if p.strip()]
    while len(parts) < 6:
        parts.append("90")
    value = ",".join(parts[:6])
    store.push_command(devs[0]["mac"], "pose", value)
    store.add_log("system", f"执行姿态：{value}")
    return {"ok": True, "angles": value}


class LedIn(BaseModel):
    value: str = "255,255,255"


@app.post("/api/device/led")
def api_device_led(body: LedIn):
    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
    if not devs:
        raise HTTPException(404, "没有绑定设备")
    store.push_command(devs[0]["mac"], "led", body.value)
    store.add_log("system", f"灯效：{body.value}")
    return {"ok": True}


@app.get("/actions", response_class=None)
async def actions_page():
    from pathlib import Path as _P

    p = _P(__file__).resolve().parent.parent / "static" / "actions.html"
    if p.exists():
        return Response(content=p.read_text(encoding="utf-8"),
                        media_type="text/html; charset=utf-8")
    return Response(content="actions.html 缺失", status_code=500)
'''
    M.write_text(m, encoding="utf-8")
    print("main.py: 已加动作接口")
else:
    print("main.py: 已存在")

ast.parse(M.read_text(encoding="utf-8"))
print("语法 OK")
