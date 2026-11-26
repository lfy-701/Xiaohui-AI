"""给控制台加多用户账号与角色（admin / viewer）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"D:\AI-Companion-shared\xiaohui-ai\console")

# ---------------------------------------------------------------- db.py
db = REPO / "app" / "db.py"
t = db.read_text(encoding="utf-8")

if "CREATE TABLE IF NOT EXISTS users" not in t:
    anchor = 'def init_db() -> None:'
    idx = t.index(anchor)
    end = t.index("\n\n\n", idx)
    block = t[idx:end]

    new_users = '''
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
        )'''
    # 插到 init_db 里最后一个 conn.executescript 之后
    if "conn.execute(" in block:
        pos = block.rindex(")")
    block_new = block + "\n" + new_users
    t = t[:idx] + block_new + t[end:]
    print("db.py: users 表已加入 init_db")

    helpers = '''


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
'''
    t = t.rstrip() + helpers
    db.write_text(t, encoding="utf-8")
    print("db.py: 用户函数已追加")
else:
    print("db.py: 已存在，跳过")
