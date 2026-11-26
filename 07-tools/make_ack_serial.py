"""避免声音重叠：查询提示音改为「播完再查」，串行执行而不是并发。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
files = [
    VS / "plugins_func" / "functions" / "get_weather.py",
    VS / "plugins_func" / "functions" / "get_news_from_chinanews.py",
]

OLD = "        _aio.run_coroutine_threadsafe(_ack_fn(conn, \"正在为您查询，请稍等。\"), _loop)"
NEW = ("        _fut = _aio.run_coroutine_threadsafe(\n"
       "            _ack_fn(conn, \"正在为您查询，请稍等。\"), _loop\n"
       "        )\n"
       "        _fut.result(timeout=10)   # 等提示音播完再查，避免两声叠在一起")

for f in files:
    if not f.exists():
        print(f"⚠ 跳过 {f.name}")
        continue
    t = f.read_text(encoding="utf-8")
    if OLD not in t:
        print(f"{f.name}: 未找到并发调用（可能已改）")
        continue
    t = t.replace(OLD, NEW, 1)
    f.write_text(t, encoding="utf-8")
    ast.parse(t)
    print(f"{f.name}: 已改为串行（提示音播完再查）")

# 新闻插件里旧的多行版本也要处理
OLD2 = """        _aio.run_coroutine_threadsafe(
            _ack_fn(conn, "正在为您查询，请稍等。"), _loop
        )"""
for f in files:
    t = f.read_text(encoding="utf-8")
    if OLD2 in t:
        t = t.replace(OLD2, NEW.replace("        _fut", "        _fut"), 1)
        f.write_text(t, encoding="utf-8")
        ast.parse(t)
        print(f"{f.name}: 已修正多行版本")
