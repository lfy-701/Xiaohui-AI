"""插入 _date_answer（若缺失）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

if "def _date_answer" in t:
    print("已存在")
    sys.exit(0)

FN = '_DATE_WEEK = "一二三四五六日"\n\n\n' + '''def _date_answer(text: str):
    """日期/星期问题直接算，避免模型算错。"""
    import datetime as _dt
    import re as _re

    t = (text or "").strip()
    if not t:
        return None

    today = _dt.date.today()
    ask_week = any(k in t for k in ("星期", "周几", "礼拜"))

    if ask_week:
        for kw, delta in (("明天", 1), ("昨天", -1), ("今天", 0), ("今日", 0)):
            if kw in t:
                d = today + _dt.timedelta(days=delta)
                return f"{kw}是 {d.year}年{d.month}月{d.day}日，星期{_DATE_WEEK[d.weekday()]}。"

    m = _re.search(r"(20\\d{2})\\s*[年\\-/]\\s*(\\d{1,2})\\s*[月\\-/]\\s*(\\d{1,2})", t)
    if m:
        y, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = _dt.date(y, mm, dd)
        except ValueError:
            return None
        return f"{y}年{mm}月{dd}日是星期{_DATE_WEEK[d.weekday()]}。"

    m2 = _re.search(r"(\\d{1,2})\\s*月\\s*(\\d{1,2})\\s*[日号]?", t)
    if m2 and ask_week:
        mm, dd = int(m2.group(1)), int(m2.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            try:
                d = _dt.date(today.year, mm, dd)
            except ValueError:
                return None
            return f"{d.year}年{d.month}月{d.day}日是星期{_DATE_WEEK[d.weekday()]}。"

    if any(k in t for k in ("今天几号", "今天日期", "今天多少号", "今天星期几")):
        return f"今天是 {today.year}年{today.month}月{today.day}日，星期{_DATE_WEEK[today.weekday()]}。"

    return None


'''

idx = t.find("def _device_cmd_from_text")
if idx < 0:
    print("⚠ 未找到插入点")
    sys.exit(1)
t = t[:idx] + FN + t[idx:]
P.write_text(t, encoding="utf-8")
ast.parse(t)
print("已插入 _date_answer；语法 OK")
