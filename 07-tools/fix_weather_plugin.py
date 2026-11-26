"""天气插件改用 Open-Meteo（免密钥、稳定），替换掉会失败的 key/爬页方案。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\plugins_func\functions\get_weather.py")
t = F.read_text(encoding="utf-8")

start = t.find('    api_host = conn.config["plugins"]["get_weather"]')
end = t.find("    weather_report = f\"您查询的位置是")
if start < 0 or end < 0:
    print("⚠ 未找到替换区间")
    sys.exit(1)

NEW = '''    # ---- 城市解析：默认东莞，支持常见城市 ----
    default_location = "东莞"
    try:
        default_location = conn.config["plugins"]["get_weather"].get("default_location") or default_location
    except Exception:
        pass

    CITIES = {
        "东莞": (23.0207, 113.7518), "广州": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579), "北京": (39.9042, 116.4074),
        "上海": (31.2304, 121.4737), "杭州": (30.2741, 120.1551),
        "成都": (30.5728, 104.0668), "武汉": (30.5928, 114.3055),
        "西安": (34.3416, 108.9398), "南京": (32.0603, 118.7969),
        "重庆": (29.5630, 106.5516), "苏州": (31.2989, 120.5853),
    }
    WEATHER_CN = {
        0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "有雾", 48: "雾",
        51: "小毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 61: "小雨", 63: "中雨",
        65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨",
        81: "强阵雨", 82: "暴雨", 95: "雷阵雨", 96: "雷阵雨伴冰雹",
    }

    city_name = (location or default_location or "东莞").strip()
    lat, lon = CITIES.get(city_name, CITIES["东莞"])
    if city_name not in CITIES:
        # 不在表里就用地理编码兜底
        try:
            import httpx as _hx

            with _hx.Client(timeout=10.0) as c:
                g = c.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city_name, "count": 1, "language": "zh", "format": "json"},
                ).json()
            r0 = (g.get("results") or [])
            if r0:
                lat, lon = r0[0]["latitude"], r0[0]["longitude"]
                city_name = r0[0].get("name") or city_name
        except Exception:
            pass

    # ---- 取当前天气 ----
    import httpx

    try:
        with httpx.Client(timeout=12.0) as c:
            w = c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "Asia/Shanghai",
                },
            ).json()
    except Exception as e:
        logger.bind(tag=TAG).warning(f"天气请求失败: {e}")
        return ActionResponse(Action.REQLLM, "抱歉，天气服务暂时连不上，等一下再问我。", None)

    cur = w.get("current") or {}
    temp = cur.get("temperature_2m")
    if temp is None:
        return ActionResponse(Action.REQLLM, "抱歉，天气数据暂时拿不到，等一下再问我。", None)

    code = int(cur.get("weather_code") or 2)
    desc = WEATHER_CN.get(code, "多云")
    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")

'''

t = t[:start] + NEW + t[end:]

# 替换后面拼装报告的部分
old_report_start = t.find('    weather_report = f"您查询的位置是：')
if old_report_start > 0:
    old_report_end = t.find("return ActionResponse(", old_report_start)
    if old_report_end > 0:
        NEW_REPORT = '''    weather_report = (
        f"{city_name}现在{desc}，气温{temp:.0f}度，"
        f"湿度{hum}%，风{wind}公里每小时。"
    )

    '''
        t = t[:old_report_start] + NEW_REPORT + t[old_report_end:]

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("天气插件已改为 Open-Meteo；语法 OK")
