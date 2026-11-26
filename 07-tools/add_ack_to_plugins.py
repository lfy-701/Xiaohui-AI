"""在天气/新闻插件执行前，先播一句「正在为您查询」。

插件是同步函数（def），运行在 executor 线程里；这里用 run_coroutine_threadsafe
把提示音投递到主事件循环执行，不阻塞查询本身。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")

ACK_SNIPPET = '''    # 执行前先告知用户在查询（不阻塞，投递到事件循环）
    try:
        import asyncio as _aio

        from core.handle.receiveAudioHandle import _speak_ack as _ack_fn

        _loop = getattr(conn, "loop", None)
        if _loop is None:
            import asyncio as _a
            _loop = _a.get_event_loop()
        _aio.run_coroutine_threadsafe(_ack_fn(conn, "正在为您查询，请稍等。"), _loop)
    except Exception:
        pass
'''

targets = [
    (VS / "plugins_func" / "functions" / "get_weather.py", "def get_weather(conn"),
    (VS / "plugins_func" / "functions" / "get_news_from_chinanews.py", "def get_news_from_chinanews("),
]

for path, marker in targets:
    if not path.exists():
        print(f"⚠ 跳过 {path.name}（不存在）")
        continue
    t = path.read_text(encoding="utf-8")
    if "正在为您查询" in t:
        print(f"{path.name}: 已存在")
        continue

    lines = t.split("\n")
    fn_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith(marker):
            fn_idx = i
            break
    if fn_idx is None:
        print(f"⚠ {path.name}: 未找到函数")
        continue

    # 函数体第一行（可能是 """docstring"""）
    insert_at = fn_idx + 1
    stripped = lines[insert_at].strip()
    if stripped.startswith('"""'):
        if stripped.count('"""') < 2:
            j = insert_at + 1
            while j < len(lines) and '"""' not in lines[j]:
                j += 1
            insert_at = j + 1
        else:
            insert_at += 1

    lines[insert_at:insert_at] = ACK_SNIPPET.split("\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    ast.parse(path.read_text(encoding="utf-8"))
    print(f"{path.name}: 已加查询提示")
