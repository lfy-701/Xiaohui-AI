"""专区本地工具：时间、天气、新闻（供 DeepSeek function calling 调用）。"""
import datetime as _dt
import json
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

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "查询今天的日期和星期，或指定日期是星期几。用户问今天几号、星期几、某天是星期几时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "可选，格式 YYYY-MM-DD 或 MM-DD；不填表示今天",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某个城市当前的天气和气温。用户问天气、冷不冷、热不热、多少度时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，例如 东莞、广州、北京；不填默认东莞",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "获取最近的真实新闻标题（中国新闻网）。用户问今天有什么新闻、最近发生了什么时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "要几条，默认 3，最多 5",
                    }
                },
            },
        },
    },
]


def get_current_time(date: str = "") -> str:
    today = _dt.date.today()
    now = _dt.datetime.now()
    d = today
    if date:
        try:
            m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", date.strip())
            if m:
                d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                m2 = re.match(r"^(\d{1,2})-(\d{1,2})$", date.strip())
                if m2:
                    d = _dt.date(today.year, int(m2.group(1)), int(m2.group(2)))
        except Exception:
            d = today

    if d == today:
        return (f"今天是{d.year}年{d.month}月{d.day}日，星期{WEEK[d.weekday()]}，"
                f"现在{now.hour:02d}:{now.minute:02d}。")
    return f"{d.year}年{d.month}月{d.day}日是星期{WEEK[d.weekday()]}。"


def get_weather(city: str = "东莞") -> str:
    city = (city or "东莞").strip()
    lat, lon = CITIES.get(city, CITIES["东莞"])
    if city not in CITIES:
        try:
            with httpx.Client(timeout=8.0) as c:
                g = c.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "zh", "format": "json"},
                ).json()
            r0 = g.get("results") or []
            if r0:
                lat, lon = r0[0]["latitude"], r0[0]["longitude"]
                city = r0[0].get("name") or city
        except Exception:
            pass

    try:
        with httpx.Client(timeout=6.0) as c:
            w = c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "Asia/Shanghai",
                },
            ).json()
        cur = w.get("current") or {}
        temp = cur.get("temperature_2m")
        if temp is None:
            raise ValueError("open-meteo 没有返回气温")
        desc = WEATHER_CN.get(int(cur.get("weather_code") or 2), "多云")
        return (f"{city}现在{desc}，气温{temp:.0f}度，"
                f"湿度{cur.get('relative_humidity_2m')}%，"
                f"风{cur.get('wind_speed_10m')}公里每小时。")
    except Exception:
        # open-meteo 在国内偶发 DNS 污染，换国内源再试
        from app.services.fast_answers import _cn_weather

        return _cn_weather(city) or "天气数据暂时拿不到。"


_NEWS_CACHE = {"at": 0.0, "items": []}


def get_news(count: int = 3) -> str:
    import time as _t

    try:
        n = max(1, min(int(count or 3), 5))
    except Exception:
        n = 3

    # 10 分钟缓存：RSS 抓取较慢，重复问不重复抓
    if _NEWS_CACHE["items"] and _t.time() - _NEWS_CACHE["at"] < 600:
        return "；".join(_NEWS_CACHE["items"][:n])
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as c:
            r = c.get("https://www.chinanews.com.cn/rss/scroll-news.xml")
            xml = r.text
    except Exception:
        return "新闻暂时查不到。"

    titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", xml)
    if len(titles) < 2:
        titles = re.findall(r"<title>(.+?)</title>", xml)
    bad = ("即时新闻", "滚动新闻", "中国新闻网", "中新网", "首页", "新闻中心")
    seen, clean = set(), []
    for x in titles:
        s = x.strip()
        if not s or any(b in s for b in bad) or s in seen:
            continue
        seen.add(s)
        clean.append(s)
    if not clean:
        return "新闻暂时查不到。"
    _NEWS_CACHE["at"] = _t.time()
    _NEWS_CACHE["items"] = clean
    return "；".join(clean[:n])


def execute_tool(name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments or "{}")
    except Exception:
        args = {}
    try:
        if name == "get_current_time":
            return get_current_time(args.get("date", ""))
        if name == "get_weather":
            return get_weather(args.get("city", "东莞"))
        if name == "get_news":
            return get_news(args.get("count", 3))
    except Exception as e:
        return f"工具执行失败: {e}"
    return "未知工具。"
