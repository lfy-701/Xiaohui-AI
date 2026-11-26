"""补回被覆盖的 _date_answer，并让澄清只对「像指令」的短句生效。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

DATE_FN = '''_DATE_WEEK = "一二三四五六日"


def _date_answer(text: str):
    """日期/星期问题直接算，避免模型算错。"""
    import datetime as _dt
    import re as _re

    t = (text or "").strip()
    if not t:
        return None

    today = _dt.date.today()
    if not any(k in t for k in ("星期", "周几", "礼拜", "几号", "几月", "日期", "几")]
        and "几" not in t:
        pass

    # 相对日期
    if any(k in t for k in ("星期", "周几", "礼拜")):
        for kw, delta in (("明天", 1), ("昨天", -1), ("今天", 0), ("今日", 0)):
            if kw in t:
                d = today + _dt.timedelta(days=delta)
                return f"{kw}是 {d.year}年{d.month}月{d.day}日，星期{_DATE_WEEK[d.weekday()]}。"

    # YYYY年M月D日 / YYYY-M-D
    m = _re.search(r"(20\\d{2})\\s*[年\\-/]\\s*(\\d{1,2})\\s*[月\\-/]\\s*(\\d{1,2})", t)
    if m:
        y, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = _dt.date(y, mm, dd)
        except ValueError:
            return None
        return f"{y}年{mm}月{dd}日是星期{_DATE_WEEK[d.weekday()]}。"

    # M月D日（按今年）
    m2 = _re.search(r"(\\d{1,2})\\s*月\\s*(\\d{1,2})\\s*[日号]?", t)
    if m2:
        mm, dd = int(m2.group(1)), int(m2.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            try:
                d = _dt.date(today.year, mm, dd)
            except ValueError:
                return None
            if any(k in t for k in ("星期", "周几", "礼拜")):
                return f"{d.year}年{d.month}月{d.day}日是星期{_DATE_WEEK[d.weekday()]}。"
            return f"{d.year}年{d.month}月{d.day}日。"

    if any(k in t for k in ("今天几号", "今天日期", "今天多少号", "今天星期")):
        return f"今天是 {today.year}年{today.month}月{today.day}日，星期{_DATE_WEEK[today.weekday()]}。"

    return None


'''

if "_date_answer" not in t:
    idx = t.find("def _device_cmd_from_text")
    if idx < 0:
        print("⚠ 未找到插入点")
        sys.exit(1)
    t = t[:idx] + DATE_FN + t[idx:]
    print("已补回 _date_answer")

# 澄清：排除常见问候/短句
old_clarify = "        if 1 <= len(_txt.strip()) <= 5 and not any(ch in _txt for ch in '?？吗呢啊'):"
new_clarify = ("        _short = _txt.strip()\n"
               "        _greet = ('你好', '您好', '谢谢', '再见', '在吗', '小慧', '哈喽', '嗨', '早', '晚安', '嗯', '好')\n"
               "        if (1 <= len(_short) <= 5 and not any(ch in _short for ch in '?？吗呢啊')\n"
               "                and not any(w in _short for w in _greet)):")
if old_clarify in t:
    t = t.replace(old_clarify, new_clarify, 1)
    print("澄清已排除问候语")

P.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
