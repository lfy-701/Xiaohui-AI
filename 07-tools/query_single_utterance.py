"""查询直通重做：
1) 放到意图处理之前（插件不会再抢走）
2) 一次合成整句播报（不再分两段、不再隔着 1 秒）
3) 去掉插件里的提示音，避免重复
"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VS = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
F = VS / "core" / "handle" / "receiveAudioHandle.py"
lines = F.read_text(encoding="utf-8").split("\n")

# ---------- 1) 重写 _handle_query_cmd ----------
start = end = None
for i, ln in enumerate(lines):
    if ln.startswith("async def _handle_query_cmd"):
        start = i
    elif start is not None and ln.startswith("async def ") and i > start:
        end = i
        break
if start is None or end is None:
    print("⚠ 未找到 _handle_query_cmd")
    sys.exit(1)

FN = '''async def _handle_query_cmd(conn, text: str) -> bool:
    """天气 / 新闻：查完一次性播报（不分段、不重复提示）。"""
    import re as _re

    import httpx as _httpx

    t = (text or "").strip()
    if not t:
        return False

    is_weather = any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度"))
    is_news = any(k in t for k in ("新闻", "头条", "发生了什么", "有什么新鲜事"))
    if not (is_weather or is_news):
        return False

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
                raise ValueError("no temp")
            desc = WEATHER_CN.get(int(cur.get("weather_code") or 2), "多云")
            hum = cur.get("relative_humidity_2m")
            wind = cur.get("wind_speed_10m")
            say = f"{city}现在{desc}，气温{temp:.0f}度，湿度{hum}%，风{wind}公里每小时。"
        except Exception:
            say = "抱歉，天气暂时查不到，等一下再问我一次好吗。"
        await _speak_ack(conn, say)
        return True

    # 新闻
    try:
        with _httpx.Client(timeout=12.0, follow_redirects=True) as c:
            r = c.get("https://www.chinanews.com.cn/rss/scroll-news.xml")
            xml = r.text
        titles = _re.findall(r"<title><!\\[CDATA\\[(.+?)\\]\\]></title>", xml)
        if len(titles) < 2:
            titles = _re.findall(r"<title>(.+?)</title>", xml)
        bad = ("即时新闻", "滚动新闻", "中国新闻网", "中新网", "首页", "新闻中心")
        seen, clean = set(), []
        for x in titles:
            s = x.strip()
            if not s or any(b in s for b in bad) or s in seen:
                continue
            seen.add(s)
            clean.append(s)
        if not clean:
            raise ValueError("no news")
        say = "给你念三条。第一条，" + clean[0] + "。第二条，" + clean[1] + "。第三条，" + clean[2] + "。"
    except Exception:
        say = "抱歉，新闻暂时查不到，等会儿再试试。"
    await _speak_ack(conn, say)
    return True


'''

lines[start:end] = FN.split("\n")
print("已重写 _handle_query_cmd（单次整句播报）")

# ---------- 2) 把调用移到意图处理之前 ----------
src = "\n".join(lines)
# 移除原调用
lines = [ln for ln in lines if "_handle_query_cmd(conn, text)" not in ln or ln.strip().startswith("async def")]
src = "\n".join(lines)

# 找到 handle_user_intent 调用
idx = src.find("intent_handled = await handle_user_intent(conn, text)")
if idx < 0:
    print("⚠ 未找到意图处理调用")
else:
    indent = " " * (len(src[:idx].split("\n")[-1]) - len(src[:idx].split("\n")[-1].lstrip()))
    inject = (
        f"{indent}# 天气/新闻直通：先于意图处理，保证由我们自己播报\n"
        f"{indent}try:\n"
        f"{indent}    if await _handle_query_cmd(conn, text):\n"
        f"{indent}        return\n"
        f"{indent}except Exception:\n"
        f"{indent}    pass\n\n"
    )
    src = src[:idx] + inject + src[idx:]
    print("已把查询直通移到意图处理之前")

F.write_text(src, encoding="utf-8")
ast.parse(src)

# ---------- 3) 去掉插件里的提示音 ----------
for name in ("get_weather.py", "get_news_from_chinanews.py"):
    p = VS / "plugins_func" / "functions" / name
    t = p.read_text(encoding="utf-8")
    t2 = re.sub(r"[ \t]*# 查询前先回应一句.*?pass\n\n", "", t, flags=re.S)
    t2 = re.sub(r"[ \t]*# 执行前先告知用户在查询.*?pass\n\n", "", t2, flags=re.S)
    if "_speak_ack" in t2:
        t2 = re.sub(r"[ \t]*try:\n[ \t]*import asyncio as _aio.*?_fut\.result\(timeout=10\)[^\n]*\n[ \t]*except Exception:\n[ \t]*pass\n\n",
                    "", t2, flags=re.S)
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        ast.parse(t2)
        print(f"{name}: 已移除插件内提示音")

print("完成")
