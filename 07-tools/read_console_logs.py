"""读控制台数据库日志，确认设备是否请求 OTA / 心跳。"""
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

db = r"D:\AI-Companion-shared\xiaohui-ai\console\data\console.db"
con = sqlite3.connect(db)
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("表:", tables)

log_table = next((t for t in tables if "log" in t.lower()), None)
if not log_table:
    raise SystemExit("没有日志表")

cur.execute(f"PRAGMA table_info({log_table})")
cols = [r[1] for r in cur.fetchall()]
print("字段:", cols)

cur.execute(f"SELECT * FROM {log_table} ORDER BY rowid DESC LIMIT 15")
rows = cur.fetchall()
for row in rows:
    rec = dict(zip(cols, row))
    ts = rec.get("ts") or rec.get("created_at") or rec.get("time") or 0
    msg = rec.get("message") or rec.get("msg") or rec.get("text") or ""
    when = time.strftime("%H:%M:%S", time.localtime(ts)) if isinstance(ts, (int, float)) and ts else str(ts)
    print(f"  {when}  {str(msg)[:90]}")
