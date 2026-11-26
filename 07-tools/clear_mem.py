import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

db = r"D:\AI-Companion-shared\xiaohui-ai\kb-service\data\memory.db"
con = sqlite3.connect(db)

# 清空记忆条目与历史（保留表结构）
for t in ("memory_facts", "facts", "fact_history"):
    try:
        n = con.execute("DELETE FROM " + t).rowcount
        print("  已清理", t, n, "行")
    except Exception as e:
        pass

# 尝试常见表名
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
for t in tabs:
    if "fact" in t.lower() or "memor" in t.lower():
        try:
            n = con.execute("DELETE FROM " + t).rowcount
            if n:
                print("  已清理", t, n, "行")
        except Exception:
            pass

con.commit()
for t in tabs:
    if "fact" in t.lower() or "memor" in t.lower():
        n = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        print("  ", t, "剩余", n, "行")
