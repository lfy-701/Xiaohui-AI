"""控制台：天气支持任意城市（地理编码）+ 网页对话接回大模型专区。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = F.read_text(encoding="utf-8")

if "_extract_city_console" not in t:
    HELPER = '''

def _extract_city_console(text: str, default: str = "东莞") -> str:
    """从「杭州天气怎么样」里提取城市名。"""
    import re as _re

    noise = ("今天", "明天", "现在", "今晚", "天气", "气温", "温度", "怎么样", "如何",
             "冷不冷", "热不热", "多少度", "几度", "会不会下雨", "下雨吗", "的", "呢",
             "吗", "啊", "呀", "帮我查", "查一下", "看一下")
    s = text or ""
    for w in noise:
        s = s.replace(w, " ")
    for part in sorted(_re.findall(r"[\\u4e00-\\u9fa5]{2,6}", s), key=len, reverse=True):
        if part not in ("查询", "请问", "告诉", "我想", "知道"):
            return part
    return default


def _geocode_console(city: str):
    """城市名 → (名称, 纬度, 经度)。失败返回东莞。"""
    import httpx as _hx

    try:
        with _hx.Client(timeout=8.0) as c:
            g = c.get("https://geocoding-api.open-meteo.com/v1/search",
                      params={"name": city, "count": 1, "language": "zh", "format": "json"}).json()
        r0 = g.get("results") or []
        if r0:
            return r0[0].get("name") or city, r0[0]["latitude"], r0[0]["longitude"]
    except Exception:
        pass
    return "东莞", 23.0207, 113.7518
'''
    idx = t.find("def _weather_answer")
    t = t[:idx] + HELPER.strip() + "\n\n\n" + t[idx:]

old = '''    # 城市：默认东莞；尝试从文本里找已知城市名
    city = os.getenv("XIAOHUI_DEFAULT_CITY", "东莞")
    lat, lon = 23.0207, 113.7518          # 东莞
    for name, la, lo in (
        ("东莞", 23.0207, 113.7518), ("广州", 23.1291, 113.2644),
        ("深圳", 22.5431, 114.0579), ("北京", 39.9042, 116.4074),
        ("上海", 31.2304, 121.4737), ("杭州", 30.2741, 120.1551),
    ):
        if name in t:
            city, lat, lon = name, la, lo
            break'''

new = '''    # 城市：从话里提取，支持全国任意城市（地理编码兜底）
    city = _extract_city_console(t, os.getenv("XIAOHUI_DEFAULT_CITY", "东莞"))
    city, lat, lon = _geocode_console(city)'''

if old in t:
    t = t.replace(old, new, 1)
    print("天气：已支持任意城市")
else:
    print("⚠ 天气城市块未匹配")

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("语法 OK")
