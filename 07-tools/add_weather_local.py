"""天气本地直算（Open-Meteo），保证打字问答拿到一致、真实的气温。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

if "_weather_answer" in t:
    print("已存在")
    sys.exit(0)

helper = '''

WEATHER_CODE_CN = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "有雾", 48: "有雾", 51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨", 95: "雷阵雨", 96: "雷阵雨伴冰雹",
}


def _weather_answer(text: str):
    """天气问题直接查 Open-Meteo，返回话术；不相关返回 None。"""
    import re as _re

    import httpx as _httpx

    t = (text or "").strip()
    if not t or not any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度")):
        return None

    city = os.getenv("XIAOHUI_DEFAULT_CITY", "东莞")
    m = _re.search(r"([\\u4e00-\\u9fa5]{2,6})(?:今天|明天|现在|的)?(?:天气|气温|温度)", t)
    if m:
        cand = m.group(1)
        if cand not in ("今天", "明天", "现在", "这边", "那里", "外面"):
            city = cand

    try:
        with _httpx.Client(timeout=12.0) as c:
            g = c.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
            ).json()
            results = g.get("results") or []
            if not results:
                return None
            lat, lon = results[0]["latitude"], results[0]["longitude"]
            name = results[0].get("name") or city
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
        hum = cur.get("relative_humidity_2m")
        code = cur.get("weather_code")
        wind = cur.get("wind_speed_10m")
        desc = WEATHER_CODE_CN.get(int(code), "多云") if code is not None else "多云"
        if temp is None:
            return None
        return (f"{name}现在{desc}，气温{temp:.1f}度，湿度{hum}%，"
                f"风{wind}公里每小时。")
    except Exception:
        return None

'''

idx = t.find("def _date_answer")
if idx < 0:
    print("⚠ 未找到插入点")
    sys.exit(1)
t = t[:idx] + helper.strip() + "\n\n\n" + t[idx:]

# 在 chat 里优先用天气直算（放在日期之后）
lines = t.split("\n")
target = None
for i, ln in enumerate(lines):
    if "'model': 'date'" in ln:
        target = i + 2
        break
if target is None:
    print("⚠ 未找到日期分支")
    sys.exit(1)

block = [
    "    # 天气直接查 Open-Meteo，避免模型编温度",
    "    try:",
    "        _w_reply = _weather_answer(str(getattr(body, 'text', '') or ''))",
    "        if _w_reply:",
    "            return {'reply': _w_reply, 'model': 'weather', 'session_id': (getattr(body, 'session_id', '') or '')}",
    "    except Exception:",
    "        pass",
]
if "'model': 'weather'" not in "\n".join(lines):
    lines[target:target] = block
    t = "\n".join(lines)
    P.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("已接入天气直算")
else:
    print("已存在天气分支")
