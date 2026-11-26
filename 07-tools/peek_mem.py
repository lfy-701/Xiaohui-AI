import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

db = r"D:\AI-Companion-shared\xiaohui-ai\kb-service\data\memory.db"
con = sqlite3.connect(db)
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("  表:", tabs)

for t in tabs:
    if "mem" in t.lower() or "fact" in t.lower():
        n = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        print("   ", t, n, "行")
        for row in con.execute("SELECT * FROM " + t + " LIMIT 5"):
            print("      ", str(row)[:110])
