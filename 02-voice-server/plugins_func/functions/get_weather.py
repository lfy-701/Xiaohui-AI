import requests
from bs4 import BeautifulSoup
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.util import get_ip_info

TAG = __name__
logger = setup_logging()

GET_WEATHER_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "获取某个地点的天气，用户应提供一个位置，比如用户说杭州天气，参数为：杭州。"
            "如果用户说的是省份，默认用省会城市。如果用户说的不是省份或城市而是一个地名，默认用该地所在省份的省会城市。"
            "如果用户没有指明地点，说“天气怎么样”，”今天天气如何“，location参数为空"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "地点名，例如杭州。可选参数，如果不提供则不传",
                },
                "lang": {
                    "type": "string",
                    "description": "返回用户使用的语言code，例如zh_CN/zh_HK/en_US/ja_JP等，默认zh_CN",
                },
            },
            "required": ["lang"],
        },
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    )
}

# 天气代码 https://dev.qweather.com/docs/resource/icons/#weather-icons
WEATHER_CODE_MAP = {
    "100": "晴",
    "101": "多云",
    "102": "少云",
    "103": "晴间多云",
    "104": "阴",
    "150": "晴",
    "151": "多云",
    "152": "少云",
    "153": "晴间多云",
    "300": "阵雨",
    "301": "强阵雨",
    "302": "雷阵雨",
    "303": "强雷阵雨",
    "304": "雷阵雨伴有冰雹",
    "305": "小雨",
    "306": "中雨",
    "307": "大雨",
    "308": "极端降雨",
    "309": "毛毛雨/细雨",
    "310": "暴雨",
    "311": "大暴雨",
    "312": "特大暴雨",
    "313": "冻雨",
    "314": "小到中雨",
    "315": "中到大雨",
    "316": "大到暴雨",
    "317": "暴雨到大暴雨",
    "318": "大暴雨到特大暴雨",
    "350": "阵雨",
    "351": "强阵雨",
    "399": "雨",
    "400": "小雪",
    "401": "中雪",
    "402": "大雪",
    "403": "暴雪",
    "404": "雨夹雪",
    "405": "雨雪天气",
    "406": "阵雨夹雪",
    "407": "阵雪",
    "408": "小到中雪",
    "409": "中到大雪",
    "410": "大到暴雪",
    "456": "阵雨夹雪",
    "457": "阵雪",
    "499": "雪",
    "500": "薄雾",
    "501": "雾",
    "502": "霾",
    "503": "扬沙",
    "504": "浮尘",
    "507": "沙尘暴",
    "508": "强沙尘暴",
    "509": "浓雾",
    "510": "强浓雾",
    "511": "中度霾",
    "512": "重度霾",
    "513": "严重霾",
    "514": "大雾",
    "515": "特强浓雾",
    "900": "热",
    "901": "冷",
    "999": "未知",
}


def fetch_city_info(location, api_key, api_host):
    url = f"https://{api_host}/geo/v2/city/lookup?key={api_key}&location={location}&lang=zh"
    response = requests.get(url, headers=HEADERS).json()
    return response.get("location", [])[0] if response.get("location") else None


def fetch_weather_page(url):
    response = requests.get(url, headers=HEADERS)
    return BeautifulSoup(response.text, "html.parser") if response.ok else None


def parse_weather_info(soup):
    city_name = soup.select_one("h1.c-submenu__location").get_text(strip=True)

    current_abstract = soup.select_one(".c-city-weather-current .current-abstract")
    current_abstract = (
        current_abstract.get_text(strip=True) if current_abstract else "未知"
    )

    current_basic = {}
    for item in soup.select(
        ".c-city-weather-current .current-basic .current-basic___item"
    ):
        parts = item.get_text(strip=True, separator=" ").split(" ")
        if len(parts) == 2:
            key, value = parts[1], parts[0]
            current_basic[key] = value

    temps_list = []
    for row in soup.select(".city-forecast-tabs__row")[:7]:  # 取前7天的数据
        date = row.select_one(".date-bg .date").get_text(strip=True)
        weather_code = (
            row.select_one(".date-bg .icon")["src"].split("/")[-1].split(".")[0]
        )
        weather = WEATHER_CODE_MAP.get(weather_code, "未知")
        temps = [span.get_text(strip=True) for span in row.select(".tmp-cont .temp")]
        high_temp, low_temp = (temps[0], temps[-1]) if len(temps) >= 2 else (None, None)
        temps_list.append((date, weather, high_temp, low_temp))

    return city_name, current_abstract, current_basic, temps_list


@register_function("get_weather", GET_WEATHER_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_weather(conn, location: str = None, lang: str = "zh_CN"):

    # ---- 城市解析：默认东莞，支持常见城市 ----
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

    weather_report = (
        f"{city_name}现在{desc}，气温{temp:.0f}度，"
        f"湿度{hum}%，风{wind}公里每小时。"
    )

    return ActionResponse(Action.RESPONSE, weather_report, weather_report)
