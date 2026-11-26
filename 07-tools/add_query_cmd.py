"""语音查询直通：天气 / 新闻。

流程：先播「正在为您查询…」→ 取数据 → 播报结果；取不到则说抱歉。
不经过模型，数据真实、时延稳定。
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
lines = F.read_text(encoding="utf-8").split("\n")

if "_handle_query_cmd" in "\n".join(lines):
    print("已存在")
    sys.exit(0)

FN = '''async def _handle_query_cmd(conn, text: str) -> bool:
    """天气 / 新闻：先说「正在为您查询」，再播报结果，失败则道歉。"""
    import re as _re

    import httpx as _httpx

    t = (text or "").strip()
    if not t:
        return False

    is_weather = any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度"))
    is_news = any(k in t for k in ("新闻", "头条", "发生了什么", "有什么新鲜事"))

    if not (is_weather or is_news):
        return False

    # 先回应，让用户知道在查
    try:
        await _speak_ack(conn, "正在为您查询，请稍等。")
    except Exception:
        pass

    WEATHER_CN = {
        0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "有雾", 48: "有雾",
        51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨", 61: "小雨", 63: "中雨",
        65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨",
        81: "强阵雨", 82: "暴雨", 95: "雷阵雨", 96: "雷阵雨伴冰雹",
    }

    if is_weather:
        city, lat, lon = "东莞", 23.0207, 113.7518
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
            cur = w.get("current") or {}
            temp = cur.get("temperature_2m")
            if temp is None:
                raise ValueError("no temperature")
            desc = WEATHER_CN.get(int(cur.get("weather_code") or 2), "多云")
            hum = cur.get("relative_humidity_2m")
            wind = cur.get("wind_speed_10m")
            say = f"{city}现在{desc}，气温{temp:.0f}度，湿度{hum}%，风{wind}公里每小时。"
            await _speak_ack(conn, say)
            return True
        except Exception:
            await _speak_ack(conn, "抱歉，天气暂时查不到，等下再问我一次好吗。")
            return True

    # 新闻：中国新闻网滚动 RSS
    try:
        with _httpx.Client(timeout=12.0, follow_redirects=True) as c:
            r = c.get("https://www.chinanews.com.cn/rss/scroll-news.xml")
            xml = r.text
        titles = _re.findall(r"<title><!\\[CDATA\\[(.+?)\\]\\]></title>", xml)
        if len(titles) < 2:
            titles = _re.findall(r"<title>(.+?)</title>", xml)
        titles = [x.strip() for x in titles if x.strip() and x.strip() != "滚动新闻"][:3]
        if not titles:
            raise ValueError("no news")
        say = "给你念三条：" + "；".join(titles) + "。"
        await _speak_ack(conn, say)
        return True
    except Exception:
        await _speak_ack(conn, "抱歉，新闻暂时查不到，等会儿再试试。")
        return True


'''

idx = None
for i, ln in enumerate(lines):
    if ln.startswith("async def _handle_device_cmd"):
        idx = i
        break
if idx is None:
    for i, ln in enumerate(lines):
        if ln.startswith("async def _handle_music_cmd"):
            idx = i
            break
if idx is None:
    print("⚠ 未找到插入点")
    sys.exit(1)

lines[idx:idx] = FN.split("\n")
print("已插入 _handle_query_cmd")

# 调用：放在设备指令之前（天气/新闻优先）
call = None
for i, ln in enumerate(lines):
    if "if await _handle_device_cmd(conn, text):" in ln:
        call = i
        break
if call is None:
    for i, ln in enumerate(lines):
        if "if await _handle_music_cmd(conn, text):" in ln:
            call = i
            break

if call is not None:
    indent = " " * (len(lines[call]) - len(lines[call].lstrip()))
    lines[call:call] = [
        indent + "if await _handle_query_cmd(conn, text):",
        indent + "    return",
    ]
    print("已接入查询分发")

F.write_text("\n".join(lines), encoding="utf-8")
ast.parse(F.read_text(encoding="utf-8"))
print("语法 OK")
