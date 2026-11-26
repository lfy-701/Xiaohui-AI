"""专区：注入当前日期 + 天气/日期快速回答（不花 API 额度）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

D = Path(r"D:\xiaohui-large-zone")

# ---------- 1) 新建快速回答模块 ----------
FAST = D / "app" / "services" / "fast_answers.py"
FAST.write_text('''"""确定性问题的本地回答：日期/星期、天气。不调用 DeepSeek，省额度也更快。"""

from __future__ import annotations

import datetime as _dt
import re

import httpx

WEEK = "一二三四五六日"

CITIES = {
    "东莞": (23.0207, 113.7518), "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579), "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737), "杭州": (30.2741, 120.1551),
    "成都": (30.5728, 104.0668), "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398), "南京": (32.0603, 118.7969),
}

WEATHER_CN = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "有雾", 48: "雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 61: "小雨", 63: "中雨",
    65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨",
    81: "强阵雨", 82: "暴雨", 95: "雷阵雨", 96: "雷阵雨伴冰雹",
}


def now_context() -> str:
    """当前时间上下文，拼到 system prompt 后面。"""
    now = _dt.datetime.now()
    return (
        f"\\n\\n当前时间：{now.year}年{now.month}月{now.day}日 "
        f"星期{WEEK[now.weekday()]} {now.hour:02d}:{now.minute:02d}（北京时间）。"
        "回答日期或时间问题时以此为准。"
    )


def date_answer(text: str) -> str | None:
    """日期/星期问题直接算。"""
    t = (text or "").strip()
    if not any(k in t for k in ("今天", "明天", "昨天", "星期", "周几", "礼拜", "几号", "几月", "日期")):
        return None

    today = _dt.date.today()
    ask_week = any(k in t for k in ("星期", "周几", "礼拜"))

    if ask_week:
        for kw, delta in (("明天", 1), ("昨天", -1), ("今天", 0), ("今日", 0)):
            if kw in t:
                d = today + _dt.timedelta(days=delta)
                return f"{kw}是{d.year}年{d.month}月{d.day}日，星期{WEEK[d.weekday()]}。"

    m = re.search(r"(20\\d{2})\\s*[年\\-/]\\s*(\\d{1,2})\\s*[月\\-/]\\s*(\\d{1,2})", t)
    if m:
        y, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = _dt.date(y, mm, dd)
        except ValueError:
            return None
        return f"{y}年{mm}月{dd}日是星期{WEEK[d.weekday()]}。"

    m2 = re.search(r"(\\d{1,2})\\s*月\\s*(\\d{1,2})\\s*[日号]?", t)
    if m2 and ask_week:
        mm, dd = int(m2.group(1)), int(m2.group(2))
        try:
            d = _dt.date(today.year, mm, dd)
        except ValueError:
            return None
        return f"{d.year}年{d.month}月{d.day}日是星期{WEEK[d.weekday()]}。"

    if any(k in t for k in ("今天几号", "今天日期", "今天星期", "今天几月")):
        return f"今天是{today.year}年{today.month}月{today.day}日，星期{WEEK[today.weekday()]}。"

    return None


def weather_answer(text: str, default_city: str = "东莞") -> str | None:
    """天气问题直接查 Open-Meteo。"""
    t = (text or "").strip()
    if not any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度")):
        return None

    city = default_city
    lat, lon = CITIES.get(city, (23.0207, 113.7518))
    for name, (la, lo) in CITIES.items():
        if name in t:
            city, lat, lon = name, la, lo
            break

    try:
        with httpx.Client(timeout=8.0) as c:
            w = c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "Asia/Shanghai",
                },
            ).json()
    except Exception:
        return None

    cur = w.get("current") or {}
    temp = cur.get("temperature_2m")
    if temp is None:
        return None
    desc = WEATHER_CN.get(int(cur.get("weather_code") or 2), "多云")
    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")
    return f"{city}现在{desc}，气温{temp:.0f}度，湿度{hum}%，风{wind}公里每小时。"


def fast_answer(text: str, default_city: str = "东莞") -> tuple[str, str] | None:
    """返回 (回答, 来源) 或 None。"""
    ans = date_answer(text)
    if ans:
        return ans, "date"
    ans = weather_answer(text, default_city)
    if ans:
        return ans, "weather"
    return None
''', encoding="utf-8")
print("已创建 fast_answers.py")

# ---------- 2) chat.py：先走快速回答，并在 prompt 注入时间 ----------
C = D / "app" / "api" / "chat.py"
t = C.read_text(encoding="utf-8")

if "fast_answer" not in t:
    t = t.replace(
        "from app.services.conversation import build_messages",
        "from app.services.conversation import build_messages\nfrom app.services.fast_answers import fast_answer, now_context",
        1,
    )

    old = """    settings = request.app.state.settings
    messages = build_messages(settings, payload.message, payload.history)"""
    new = """    settings = request.app.state.settings

    # 1) 确定性回答（日期/天气）：不调用 DeepSeek，省额度也更快
    fast = fast_answer(payload.message, getattr(settings, "default_city", "东莞"))
    if fast:
        answer, source = fast
        logger.info("快速回答命中: %s", source)
        return ChatResponse(
            reply=answer,
            model="fast-" + source,
            usage=Usage(),
        )

    # 2) 注入当前时间，避免模型说"不知道今天几号"
    settings.system_prompt = settings.system_prompt + now_context()
    messages = build_messages(settings, payload.message, payload.history)"""
    if old in t:
        t = t.replace(old, new, 1)
        print("chat.py：已接入快速回答 + 时间注入")
    else:
        print("⚠ chat.py 未匹配")

    C.write_text(t, encoding="utf-8")

import ast
ast.parse(C.read_text(encoding="utf-8"))
ast.parse(FAST.read_text(encoding="utf-8"))
print("语法 OK")
