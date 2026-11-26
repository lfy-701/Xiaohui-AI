"""天气支持任意城市：从话里提取城市名，走了地理编码兜底。

同时改两处：语音服务直查、专区快速回答。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

EXTRACTOR = '''

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
    for part in sorted(_re.findall(r"[\\u4e00-\\u9fa5]{2,6}", s), key=len, reverse=True):
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

'''

# ---------------- 1) 语音服务 ----------------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

if "_extract_city" not in v:
    idx = v.find("async def _handle_query_cmd")
    v = v[:idx] + EXTRACTOR.strip() + "\n\n\n" + v[idx:]

    old = '''        city, lat, lon = "东莞", 23.0207, 113.7518
        for name, la, lo in (
            ("东莞", 23.0207, 113.7518), ("广州", 23.1291, 113.2644),
            ("深圳", 22.5431, 114.0579), ("北京", 39.9042, 116.4074),
            ("上海", 31.2304, 121.4737), ("杭州", 30.2741, 120.1551),
        ):
            if name in t:
                city, lat, lon = name, la, lo
                break'''
    new = '''        city = _extract_city(t, "东莞")
        city, lat, lon = _geocode_city(city)'''
    if old in v:
        v = v.replace(old, new, 1)
        print("语音服务：天气改为任意城市 + 地理编码")
    else:
        print("⚠ 语音天气块未匹配")

    V.write_text(v, encoding="utf-8")
    ast.parse(v)

# ---------------- 2) 专区快速回答 ----------------
Z = Path(r"D:\xiaohui-large-zone\app\services\fast_answers.py")
z = Z.read_text(encoding="utf-8")

if "_extract_city" not in z:
    idx = z.find("def weather_answer")
    z = z[:idx] + EXTRACTOR.strip() + "\n\n\n" + z[idx:]

    old2 = '''    city = default_city
    lat, lon = CITIES.get(city, (23.0207, 113.7518))
    for name, (la, lo) in CITIES.items():
        if name in t:
            city, lat, lon = name, la, lo
            break'''
    new2 = '''    city = _extract_city(t, default_city)
    if city in CITIES:
        lat, lon = CITIES[city]
    else:
        city, lat, lon = _geocode_city(city)'''
    if old2 in z:
        z = z.replace(old2, new2, 1)
        print("专区：天气改为任意城市 + 地理编码")
    else:
        print("⚠ 专区天气块未匹配")

    Z.write_text(z, encoding="utf-8")
    ast.parse(z)

print("语法 OK")
