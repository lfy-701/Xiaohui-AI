"""控制台的 SQLite 层：智能体 / 设备 / 对话日志。"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("./data/console.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                avatar TEXT DEFAULT '🐶',
                persona TEXT DEFAULT '',
                model TEXT DEFAULT 'qwen2.5:3b',
                voice TEXT DEFAULT 'zh-CN-XiaoxiaoNeural',
                language TEXT DEFAULT 'zh-CN',
                wake_word TEXT DEFAULT '你好小智',
                kb_enabled INTEGER DEFAULT 1,
                kb_topk INTEGER DEFAULT 3,
                memory_enabled INTEGER DEFAULT 1,
                temperature REAL DEFAULT 0.7,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                mac TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                agent_id TEXT,
                firmware TEXT DEFAULT '',
                ip TEXT DEFAULT '',
                last_seen REAL DEFAULT 0,
                code TEXT DEFAULT '',
                bound INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS logs (
                id TEXT PRIMARY KEY,
                agent_id TEXT,
                device_id TEXT,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_logs_agent ON logs(agent_id, at);

            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, at);

            CREATE TABLE IF NOT EXISTS firmwares (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                filename TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at REAL NOT NULL
            );
            """
        )
        # 轻量迁移：老库补列
        for stmt in (
            "ALTER TABLE devices ADD COLUMN code TEXT DEFAULT ''",
            "ALTER TABLE devices ADD COLUMN bound INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                created_at REAL NOT NULL,
                last_login REAL
            )
            """
        )


AGENT_FIELDS = (
    "name", "avatar", "persona", "model", "voice", "language", "wake_word",
    "kb_enabled", "kb_topk", "memory_enabled", "temperature",
)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for k in ("kb_enabled", "memory_enabled"):
        if k in d:
            d[k] = bool(d[k])
    return d


# ---------------------------------------------------------------- agents

def list_agents() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY updated_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    with db() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    return _row_to_dict(row) if row else None


def create_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    now = time.time()
    aid = uuid.uuid4().hex[:12]
    payload = {k: data.get(k) for k in AGENT_FIELDS if data.get(k) is not None}
    payload.setdefault("name", "新智能体")
    with db() as conn:
        cols = ["id", "created_at", "updated_at"] + list(payload.keys())
        vals = [aid, now, now] + [int(v) if isinstance(v, bool) else v for v in payload.values()]
        conn.execute(
            f"INSERT INTO agents({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", vals
        )
    return get_agent(aid)  # type: ignore


def update_agent(agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = {k: v for k, v in data.items() if k in AGENT_FIELDS and v is not None}
    if not fields:
        return get_agent(agent_id)
    sets = ",".join(f"{k}=?" for k in fields)
    vals = [int(v) if isinstance(v, bool) else v for v in fields.values()]
    vals += [time.time(), agent_id]
    with db() as conn:
        conn.execute(f"UPDATE agents SET {sets}, updated_at=? WHERE id=?", vals)
    return get_agent(agent_id)


def delete_agent(agent_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))


# ---------------------------------------------------------------- devices

def list_devices() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    out = []
    now = time.time()
    for r in rows:
        d = dict(r)
        d["online"] = (now - (d["last_seen"] or 0)) < 120
        out.append(d)
    return out


def upsert_device(mac: str, name: str = "", agent_id: str = "", firmware: str = "", ip: str = "") -> Dict[str, Any]:
    now = time.time()
    with db() as conn:
        row = conn.execute("SELECT id FROM devices WHERE mac=?", (mac,)).fetchone()
        if row:
            conn.execute(
                "UPDATE devices SET last_seen=?, firmware=COALESCE(NULLIF(?,''),firmware),"
                " ip=COALESCE(NULLIF(?,''),ip), agent_id=COALESCE(NULLIF(?,''),agent_id),"
                " name=COALESCE(NULLIF(?,''),name) WHERE mac=?",
                (now, firmware, ip, agent_id, name, mac),
            )
            did = row["id"]
        else:
            did = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO devices(id,mac,name,agent_id,firmware,ip,last_seen) VALUES (?,?,?,?,?,?,?)",
                (did, mac, name, agent_id, firmware, ip, now),
            )
    with db() as conn:
        return dict(conn.execute("SELECT * FROM devices WHERE id=?", (did,)).fetchone())


def register_device(mac: str, firmware: str = "", ip: str = "") -> Dict[str, Any]:
    """设备开机自报。首次注册分配 6 位激活码，之后复用。"""
    now = time.time()
    with db() as conn:
        row = conn.execute("SELECT * FROM devices WHERE mac=?", (mac,)).fetchone()
        if row:
            conn.execute(
                "UPDATE devices SET last_seen=?, firmware=?, ip=? WHERE mac=?",
                (now, firmware or row["firmware"], ip or row["ip"], mac),
            )
            # 老设备没有激活码的话补一个
            if not row["code"]:
                code = "%06d" % (int(uuid.uuid4().int % 1000000))
                conn.execute("UPDATE devices SET code=? WHERE mac=?", (code, mac))
            dev = dict(conn.execute("SELECT * FROM devices WHERE mac=?", (mac,)).fetchone())
        else:
            did = uuid.uuid4().hex[:12]
            code = "%06d" % (int(uuid.uuid4().int % 1000000))
            conn.execute(
                "INSERT INTO devices(id,mac,name,agent_id,firmware,ip,last_seen,code,bound)"
                " VALUES (?,?,?,?,?,?,?,?,0)",
                (did, mac, "小慧AI", "", firmware, ip, now, code),
            )
            dev = dict(conn.execute("SELECT * FROM devices WHERE mac=?", (mac,)).fetchone())
    return {
        "device_id": dev["id"],
        "code": dev["code"],
        "bound": bool(dev["bound"]),
        "agent_id": dev["agent_id"] or "",
        "name": dev["name"] or "",
    }


def bind_device(code: str, agent_id: str) -> Optional[Dict[str, Any]]:
    """按激活码把设备绑到智能体。"""
    with db() as conn:
        row = conn.execute("SELECT * FROM devices WHERE code=?", (code,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE devices SET agent_id=?, bound=1 WHERE id=?", (agent_id, row["id"])
        )
        return dict(conn.execute("SELECT * FROM devices WHERE id=?", (row["id"],)).fetchone())


def unbind_device(device_id: str) -> None:
    with db() as conn:
        conn.execute("UPDATE devices SET agent_id=NULL, bound=0 WHERE id=?", (device_id,))


def rename_device(device_id: str, name: str) -> None:
    with db() as conn:
        conn.execute("UPDATE devices SET name=? WHERE id=?", (name, device_id))


def device_config(mac: str) -> Optional[Dict[str, Any]]:
    """设备心跳时顺便拿自己的配置（绑定的智能体）。"""
    with db() as conn:
        row = conn.execute("SELECT * FROM devices WHERE mac=?", (mac,)).fetchone()
        if not row:
            return None
        agent = None
        if row["agent_id"]:
            a = conn.execute("SELECT * FROM agents WHERE id=?", (row["agent_id"],)).fetchone()
            if a:
                agent = {
                    "id": a["id"], "name": a["name"], "wake_word": a["wake_word"],
                    "voice": a["voice"], "model": a["model"],
                    "persona": a["persona"], "kb_enabled": bool(a["kb_enabled"]),
                }
    return {"device_id": row["id"], "bound": bool(row["bound"]), "agent": agent}


def delete_device(device_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM devices WHERE id=?", (device_id,))


# ---------------------------------------------------------------- logs

def add_log(role: str, text: str, agent_id: str = "", device_id: str = "") -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO logs(id,agent_id,device_id,role,text,at) VALUES (?,?,?,?,?,?)",
            (uuid.uuid4().hex[:12], agent_id, device_id, role, text, time.time()),
        )


def list_logs(agent_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    with db() as conn:
        if agent_id:
            rows = conn.execute(
                "SELECT * FROM logs WHERE agent_id=? ORDER BY at DESC LIMIT ?", (agent_id, limit)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM logs ORDER BY at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- 试聊多轮

def add_chat_message(session_id: str, agent_id: str, role: str, content: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO chat_messages(id,session_id,agent_id,role,content,at) VALUES (?,?,?,?,?,?)",
            (uuid.uuid4().hex[:12], session_id, agent_id, role, content, time.time()),
        )


def chat_history(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT role, content, at FROM chat_messages WHERE session_id=? "
            "ORDER BY at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_chat(session_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))


# ---------------------------------------------------------------- 固件

def add_firmware(version: str, filename: str, size: int, notes: str = "") -> Dict[str, Any]:
    fid = uuid.uuid4().hex[:12]
    with db() as conn:
        conn.execute(
            "INSERT INTO firmwares(id,version,filename,size,notes,created_at) VALUES (?,?,?,?,?,?)",
            (fid, version, filename, size, notes, time.time()),
        )
    return get_firmware(fid)  # type: ignore


def get_firmware(fid: str) -> Optional[Dict[str, Any]]:
    with db() as conn:
        row = conn.execute("SELECT * FROM firmwares WHERE id=?", (fid,)).fetchone()
    return dict(row) if row else None


def list_firmwares() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM firmwares ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def latest_firmware() -> Optional[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM firmwares ORDER BY created_at DESC").fetchall()
    if not rows:
        return None
    # 按版本号排序取最大
    def key(r):
        return tuple(int(x) if x.isdigit() else 0 for x in str(r["version"]).split("."))
    return dict(max(rows, key=key))


def delete_firmware(fid: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM firmwares WHERE id=?", (fid,))


# ---------------------------------------------------------------- 统计

def stats() -> Dict[str, Any]:
    now = time.time()
    today = time.strftime("%Y-%m-%d")
    with db() as conn:
        agents = conn.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"]
        devices = conn.execute("SELECT COUNT(*) c FROM devices").fetchone()["c"]
        bound = conn.execute("SELECT COUNT(*) c FROM devices WHERE bound=1").fetchone()["c"]
        online = conn.execute(
            "SELECT COUNT(*) c FROM devices WHERE last_seen > ?", (now - 120,)
        ).fetchone()["c"]
        turns = conn.execute(
            "SELECT COUNT(*) c FROM chat_messages WHERE role='user'"
        ).fetchone()["c"]
        today_turns = conn.execute(
            "SELECT COUNT(*) c FROM chat_messages WHERE role='user' AND date(at,'unixepoch','localtime')=?",
            (today,),
        ).fetchone()["c"]
        logs = conn.execute("SELECT COUNT(*) c FROM logs").fetchone()["c"]
        fws = conn.execute("SELECT COUNT(*) c FROM firmwares").fetchone()["c"]
        rows = conn.execute(
            "SELECT date(at,'unixepoch','localtime') d, COUNT(*) c FROM chat_messages "
            "WHERE role='user' GROUP BY d ORDER BY d DESC LIMIT 7"
        ).fetchall()

    day_map = {r["d"]: r["c"] for r in rows}
    days = []
    for i in range(6, -1, -1):
        d = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
        days.append({"date": d[5:], "count": day_map.get(d, 0)})

    return {
        "agents": agents,
        "devices": {"total": devices, "online": online, "bound": bound},
        "chats": {"turns": turns, "today": today_turns},
        "logs": logs,
        "firmwares": fws,
        "recent": days,
    }


def _hash_password(password: str, salt: str) -> str:
    import hashlib

    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def create_user(username: str, password: str, role: str = "viewer") -> Dict[str, Any]:
    import secrets
    import time

    uid = secrets.token_hex(8)
    salt = secrets.token_hex(8)
    with db() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, salt, role, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (uid, username.strip(), _hash_password(password, salt), salt, role, time.time()),
        )
    return {"id": uid, "username": username, "role": role}


def list_users() -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, username, role, created_at, last_login FROM users ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    import time

    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
        if not row:
            return None
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            return None
        conn.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), row["id"]))
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def delete_user(username: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM users WHERE username=?", (username.strip(),))


def set_user_password(username: str, password: str) -> None:
    import secrets

    salt = secrets.token_hex(8)
    with db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, salt=? WHERE username=?",
            (_hash_password(password, salt), salt, username.strip()),
        )


def count_users() -> int:
    with db() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def init_commands_table() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def push_command(mac: str, kind: str, value: str) -> int:
    import time
    init_commands_table()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO device_commands (mac, kind, value, created_at) VALUES (?,?,?,?)",
            (mac, kind, value, time.time()),
        )
        return int(cur.lastrowid)


def take_commands(mac: str, limit: int = 5) -> list:
    init_commands_table()
    with db() as conn:
        rows = conn.execute(
            "SELECT id, kind, value FROM device_commands WHERE mac=? AND done=0 "
            "ORDER BY id LIMIT ?",
            (mac, limit),
        ).fetchall()
        if rows:
            ids = ",".join(str(r["id"]) for r in rows)
            conn.execute("UPDATE device_commands SET done=1 WHERE id IN (" + ids + ")")
    return [{"kind": r["kind"], "value": r["value"]} for r in rows]


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


def recent_chats(limit: int = 200) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT role, content, at FROM chat_messages ORDER BY at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_memories() -> int:
    """清空错误记忆（仅清理 memory 表，不动聊天记录）。"""
    with db() as conn:
        try:
            cur = conn.execute("DELETE FROM memories")
            return cur.rowcount
        except Exception:
            return 0


def clear_all_chats() -> int:
    with db() as conn:
        cur = conn.execute("DELETE FROM chat_messages")
        return cur.rowcount


def init_config_history() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at REAL NOT NULL,
                agent_id TEXT,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                source TEXT
            )
            """
        )


def add_config_history(agent_id: str, field: str, old: str, new: str,
                       source: str = "console") -> None:
    import time

    init_config_history()
    with db() as conn:
        conn.execute(
            "INSERT INTO config_history (at, agent_id, field, old_value, new_value, source)"
            " VALUES (?,?,?,?,?,?)",
            (time.time(), agent_id, field, old, new, source),
        )


def list_config_history(limit: int = 50) -> list:
    init_config_history()
    with db() as conn:
        rows = conn.execute(
            "SELECT id, at, agent_id, field, old_value, new_value, source"
            " FROM config_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_config_history(hid: int):
    init_config_history()
    with db() as conn:
        row = conn.execute(
            "SELECT id, at, agent_id, field, old_value, new_value, source"
            " FROM config_history WHERE id=?", (hid,)
        ).fetchone()
    return dict(row) if row else None
