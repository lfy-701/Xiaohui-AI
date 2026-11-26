"""确定性问题的本地回答：日期/星期、天气。不调用 DeepSeek，省额度也更快。"""

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
        f"\n\n当前时间：{now.year}年{now.month}月{now.day}日 "
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

    m = re.search(r"(20\d{2})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})", t)
    if m:
        y, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = _dt.date(y, mm, dd)
        except ValueError:
            return None
        return f"{y}年{mm}月{dd}日是星期{WEEK[d.weekday()]}。"

    m2 = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", t)
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


# 简单 TTL 缓存：天气/新闻 10 分钟内复用，避免重复走公网
_FAST_CACHE = {}


def _cache_get(key, ttl=600):
    import time as _t
    item = _FAST_CACHE.get(key)
    if item and _t.time() - item[0] < ttl:
        return item[1]
    return None


def _cache_put(key, value):
    import time as _t
    _FAST_CACHE[key] = (_t.time(), value)


def _extract_city(text: str, default: str = "东莞") -> str:
    """从「杭州天气怎么样」这类话里提取城市名。"""
    import re as _re

    t = (text or "").strip()
    noise = (
        "今天", "明天", "现在", "今天早上", "今晚", "今天下午",
        "天气", "气温", "温度", "怎么样", "如何", "好不好", "冷不冷",
        "热不热", "多少度", "几度", "会不会下雨", "下雨吗", "有雨吗",
        "的", "呢", "吗", "啊", "呀", "帮我查", "查一下", "看一下",
    )
    s = t
    for w in noise:
        s = s.replace(w, " ")
    # 取剩下的连续中文片段，优先 2~6 字
    for part in sorted(_re.findall(r"[\u4e00-\u9fa5]{2,6}", s), key=len, reverse=True):
        if part not in ("查询", "请问", "告诉", "我想", "知道"):
            return part
    return default


def _geocode_city(city: str, default_lat: float = 23.0207,
                  default_lon: float = 113.7518):
    """城市名 → (名称, 纬度, 经度)；失败返回默认。"""
    import httpx as _hx

    try:
        with _hx.Client(timeout=8.0) as c:
            g = c.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
            ).json()
        r0 = g.get("results") or []
        if r0:
            return (r0[0].get("name") or city), r0[0]["latitude"], r0[0]["longitude"]
    except Exception:
        pass
    return city, default_lat, default_lon


_CN_HEADERS = {
    "Referer": "http://www.weather.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}

# 中国天气网城市码（toy1 检索接口对部分城市名不稳定，常用城市直接查表）
_CN_CODES = {
    "东莞": "101281601", "广州": "101280101", "深圳": "101280601",
    "北京": "101010100", "上海": "101020100", "杭州": "101210101",
    "成都": "101270101", "武汉": "101200101", "西安": "101110101",
    "南京": "101190101",
}


# open-meteo 熔断：失败后 5 分钟内直接走国内源，不再干等握手超时
_METEO_DOWN_UNTIL = 0.0
_METEO_COOLDOWN = 300.0


def _meteo_available() -> bool:
    import time as _t

    return _t.time() >= _METEO_DOWN_UNTIL


def _mark_meteo_down() -> None:
    global _METEO_DOWN_UNTIL
    import time as _t

    _METEO_DOWN_UNTIL = _t.time() + _METEO_COOLDOWN


def _mark_meteo_up() -> None:
    global _METEO_DOWN_UNTIL
    _METEO_DOWN_UNTIL = 0.0


def _cn_weather(city: str) -> str | None:
    """中国天气网兜底。

    open-meteo 的域名在国内偶发 DNS 污染（解析到不可达 IP），
    单源失败会让上层退化成「天气查不到」，所以补一条国内源。
    """
    try:
        import json as _json

        code = _CN_CODES.get(city)
        if not code:
            with httpx.Client(timeout=6.0, headers=_CN_HEADERS) as c:
                r = c.get("http://toy1.weather.com.cn/search", params={"cityname": city})
                r.encoding = "gbk"
            m = re.search(r'"ref":"(\d{9})~', r.text or "")
            if not m:
                return None
            code = m.group(1)

        with httpx.Client(timeout=6.0, headers=_CN_HEADERS) as c:
            k = c.get(f"http://d1.weather.com.cn/sk_2d/{code}.html")
        # 中国天气网这个接口以前是 GBK，2026-11 起部分节点改成 UTF-8，
        # 写死 gbk 会把「阴」解成「闃」这种乱码。两种都试，取能解析的那份。
        text = None
        for enc in ("utf-8", "gbk"):
            try:
                cand = k.content.decode(enc)
            except Exception:
                continue
            if "{" in cand and "}" in cand and "\ufffd" not in cand:
                text = cand
                break
        if text is None:
            return None
        d = _json.loads(text[text.index("{"): text.rindex("}") + 1])
        temp = float(d.get("temp"))
        desc = d.get("weather") or "多云"
        hum = d.get("SD") or "-"
        wind = ((d.get("WD") or "") + (d.get("WS") or "")).strip() or "-"
        return f"{city}现在{desc}，气温{temp:.0f}度，湿度{hum}，风{wind}。"
    except Exception:
        return None


def _meteo_weather(city: str, lat: float, lon: float) -> str | None:
    """open-meteo 单次查询（失败即熔断，交给竞速逻辑用）。"""
    if not _meteo_available():
        return None
    try:
        with httpx.Client(timeout=2.5) as c:
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
            raise ValueError("open-meteo 没有返回温度")
        desc = WEATHER_CN.get(int(cur.get("weather_code") or 2), "多云")
        hum = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        _mark_meteo_up()
        return f"{city}现在{desc}，气温{temp:.0f}度，湿度{hum}%，风{wind}公里每小时。"
    except Exception:
        _mark_meteo_down()
        return None


def _race_weather(city: str, lat: float, lon: float,
                  prefer_ms: int = 800, hard_ms: int = 2500) -> str | None:
    """open-meteo 与国内源并行竞速。

    以前是「open-meteo 6 秒超时 × 重试 2 次 → 再走国内源」，
    冷启动第一次问天气要白等 12~16 秒（2026-11-26 实测 15.9s）。
    现在两边同时发：
      · open-meteo 先在 prefer_ms 内回来就用它（数据更全）；
      · 国内源先回来，就再等一会儿 open-meteo，等不到就用国内源；
      · 全程 hard_ms 封顶。
    open-meteo 失败会熔断 5 分钟，之后只打国内源（~0.1 秒）。
    """
    import queue as _queue
    import threading
    import time as _t

    q: "_queue.Queue" = _queue.Queue()

    def _run(name, fn, *args):
        try:
            q.put((name, fn(*args)))
        except Exception:
            q.put((name, None))

    threads = []
    if _meteo_available():
        threads.append(threading.Thread(target=_run, args=("meteo", _meteo_weather, city, lat, lon),
                                        daemon=True))
    threads.append(threading.Thread(target=_run, args=("cn", _cn_weather, city), daemon=True))
    for th in threads:
        th.start()

    started = _t.time()
    deadline = started + hard_ms / 1000.0
    cn_value = None
    got = 0
    while got < len(threads):
        remain = deadline - _t.time()
        if remain <= 0:
            break
        try:
            name, value = q.get(timeout=remain)
        except _queue.Empty:
            break
        got += 1
        if not value:
            continue
        if name == "meteo":
            return value            # 主源优先
        cn_value = value
        # 国内源先到：给 open-meteo 留一点时间，别为了主源多等太久
        wait = started + prefer_ms / 1000.0 - _t.time()
        if wait <= 0:
            return cn_value
        try:
            name2, value2 = q.get(timeout=wait)
        except _queue.Empty:
            return cn_value
        if name2 == "meteo" and value2:
            return value2
        return cn_value
    return cn_value


def weather_answer(text: str, default_city: str = "东莞") -> str | None:
    """天气问题直接查（open-meteo 与国内源并行竞速）。"""
    t = (text or "").strip()
    if not any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度")):
        return None

    city = _extract_city(t, default_city)
    _cached = _cache_get("weather:" + city)
    if _cached:
        return _cached
    if city in CITIES:
        lat, lon = CITIES[city]
    else:
        city, lat, lon = _geocode_city(city)

    out = _race_weather(city, lat, lon)
    if out:
        _cache_put("weather:" + city, out)
    return out


def news_answer(text: str) -> str | None:
    """新闻问题直接返回标题，不经过模型（省一次往返）。"""
    t = (text or "").strip()
    if not any(k in t for k in ("新闻", "头条", "发生了什么", "新鲜事")):
        return None
    try:
        from app.services.tools import get_news

        items = get_news(3)
        if not items or "查不到" in items:
            return None
        parts = [x for x in items.split("；") if x.strip()][:3]
        if not parts:
            return None
        lines = "；".join(parts)
        return f"给你念三条：{lines}。"
    except Exception:
        return None


def fast_answer(text: str, default_city: str = "东莞") -> tuple[str, str] | None:
    """返回 (回答, 来源) 或 None。"""
    ans = date_answer(text)
    if ans:
        return ans, "date"
    ans = news_answer(text)
    if ans:
        return ans, "news"
    ans = weather_answer(text, default_city)
    if ans:
        return ans, "weather"
    return None


def warmup_cities(cities=("东莞", "广州", "深圳", "北京", "上海")) -> None:
    """启动时预热常用城市天气，让第一次提问也很快。"""
    import threading

    def _run():
        for c in cities:
            try:
                weather_answer(f"{c}天气", c)
            except Exception:
                pass

    threading.Thread(target=_run, name="weather-warmup", daemon=True).start()
