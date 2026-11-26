"""重写 _weather_answer：更稳的解析与容错，带错误日志。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

start = t.find("def _weather_answer(text: str):")
if start < 0:
    print("⚠ 未找到函数")
    sys.exit(1)
end = t.find("def _device_cmd_from_text", start)
if end < 0:
    print("⚠ 未找到结束位置")
    sys.exit(1)

new = '''def _weather_answer(text: str):
    """天气问题直接查 Open-Meteo（固定坐标兜底），返回话术；不相关返回 None。"""
    import httpx as _httpx

    t = (text or "").strip()
    if not t:
        return None
    if not any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度")):
        return None

    # 城市：默认东莞；尝试从文本里找已知城市名
    city = os.getenv("XIAOHUI_DEFAULT_CITY", "东莞")
    lat, lon = 23.0207, 113.7518          # 东莞
    for name, la, lo in (
        ("东莞", 23.0207, 113.7518), ("广州", 23.1291, 113.2644),
        ("深圳", 22.5431, 114.0579), ("北京", 39.9042, 116.4074),
        ("上海", 31.2304, 121.4737), ("杭州", 30.2741, 120.1551),
    ):
        if name in t:
            city, lat, lon = name, la, lo
            break

    try:
        with _httpx.Client(timeout=12.0) as c:
            w = c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "Asia/Shanghai",
                },
            ).json()
    except Exception as e:
        store.add_log("system", f"天气查询失败: {e}")
        return None

    cur = w.get("current") or {}
    temp = cur.get("temperature_2m")
    if temp is None:
        return None
    hum = cur.get("relative_humidity_2m")
    code = cur.get("weather_code")
    wind = cur.get("wind_speed_10m")
    desc = WEATHER_CODE_CN.get(int(code), "多云") if code is not None else "多云"
    return (f"{city}现在{desc}，气温{temp:.1f}度，湿度{hum}%，"
            f"风{wind}公里每小时。")


'''

t = t[:start] + new + t[end:]
P.write_text(t, encoding="utf-8")
ast.parse(t)
print("已重写 _weather_answer；语法 OK")
