"""修两个问题：
1) 日期/星期问题由服务端直接算（模型算不准，会答错还顺着用户改）
2) 空回复气泡：历史里过滤空消息 + 不再保存空回复
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = P.read_text(encoding="utf-8")

# ---------- 1) 日期解析器 ----------
if "_date_answer" not in c:
    helper = '''

_DATE_WEEK = "一二三四五六日"


def _date_answer(text: str):
    """能直接算出来的日期问题，就别让模型猜。"""
    import datetime as _dt
    import re as _re

    t = (text or "").strip()
    if not t:
        return None

    today = _dt.date.today()

    # 「今天/明天/昨天 星期几、几号」
    if any(k in t for k in ("今天", "今日", "明天", "昨天")) and any(
        k in t for k in ("星期", "周几", "礼拜", "几号", "几月"))
:
        pass
'''
    # 上面写坏了，改用直接构造（避免语法问题）
    helper = '''

_DATE_WEEK = "一二三四五六日"


def _date_answer(text: str):
    """能直接算出来的日期问题，就别让模型猜。"""
    import datetime as _dt
    import re as _re

    t = (text or "").strip()
    if not t:
        return None

    today = _dt.date.today()
    ask_week = any(k in t for k in ("星期", "周几", "礼拜", "礼六", "礼日"))

    # 相对日期
    if ask_week:
        for kw, delta in (("明天", 1), ("昨天", -1), ("今天", 0), ("今日", 0)):
            if kw in t:
                d = today + _dt.timedelta(days=delta)
                return f"{kw}是 {d.year}年{d.month}月{d.day}日，星期{_DATE_WEEK[d.weekday()]}。"

    # 具体日期：2026年12月5日 / 12月5日 / 12-5
    m = _re.search(r"(20\\d{2})\\s*[年\\-/]\\s*(\\d{1,2})\\s*[月\\-/]\\s*(\\d{1,2})", t)
    if not m:
        m2 = _re.search(r"(?<!\\d)(\\d{1,2})\\s*[月\\-/]\\s*(\\d{1,2})\\s*[日号]?", t)
        if m2:
            mm, dd = int(m2.group(1)), int(m2.group(2))
            if 1 <= mm <= 12 and 1 <= dd <= 31:
                m = None
                try:
                    d = _dt.date(today.year, mm, dd)
                except ValueError:
                    return None
                return f"{d.year}年{d.month}月{d.day}日是星期{_DATE_WEEK[d.weekday()]}。"
    if m:
        y, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = _dt.date(y, mm, dd)
        except ValueError:
            return None
        return f"{y}年{mm}月{dd}日是星期{_DATE_WEEK[d.weekday()]}。"

    # 只问今天几号
    if any(k in t for k in ("今天几号", "今天日期", "今天多少号")):
        return f"今天是 {today.year}年{today.month}月{today.day}日，星期{_DATE_WEEK[today.weekday()]}。"

    return None
'''
    idx = c.find("def _device_cmd_from_text")
    if idx > 0:
        c = c[:idx] + helper.strip() + "\n\n\n" + c[idx:]
        print("已加日期解析器")

P.write_text(c, encoding="utf-8")
ast.parse(c)

# ---------- 2) chat 里优先用日期解析 ----------
lines = c.split("\n")
target = None
for i, ln in enumerate(lines):
    if "设备指令直通" in ln:
        target = i
        break
if target is None:
    print("⚠ 未找到 chat 拦截块")
    sys.exit(1)

block = [
    "    # 日期/星期直接算，避免模型算错",
    "    try:",
    "        _date_reply = _date_answer(str(getattr(body, 'text', '') or ''))",
    "        if _date_reply:",
    "            return {'reply': _date_reply, 'model': 'date', 'session_id': getattr(body, 'session_id', '') or ''}",
    "    except Exception:",
    "        pass",
]

if "'model': 'date'" not in "\n".join(lines):
    lines[target:target] = block
    c = "\n".join(lines)
    P.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("已接入日期直算（行", target + 1, "）")

# ---------- 3) 历史接口过滤空消息 ----------
c = P.read_text(encoding="utf-8")
old = 'return {"session_id": session_id, "messages": store.chat_history(session_id, 50)}'
new = ('_msgs = [m for m in store.chat_history(session_id, 50) '
       'if str((m.get("content") if isinstance(m, dict) else "") or "").strip()]'
       '\n    return {"session_id": session_id, "messages": _msgs}')
if old in c:
    c = c.replace(old, new, 1)
    P.write_text(c, encoding="utf-8")
    ast.parse(c)
    print("历史接口：已过滤空消息")
else:
    print("历史接口：未匹配（可能已改）")
