from core.handle.sendAudioHandle import send_stt_message
from core.handle.intentHandler import handle_user_intent
from core.handle.commandHandler import try_handle_voice_command
from core.utils.output_counter import check_device_output_limit
from core.handle.abortHandle import handleAbortMessage
import time
import asyncio
from core.handle.sendAudioHandle import SentenceType
from core.utils.util import audio_to_data

TAG = __name__


# ---------------- 语音点歌（关键词直通，跳过模型） ----------------
import re as _re


def _parse_music_query(text: str):
    """识别点歌意图，返回歌名；不是点歌返回 None。"""
    if not text:
        return None
    t = text.strip()

    # 明确说了「歌/曲/音乐」的，即使动词听错也当点歌
    if any(k in t for k in ("音乐", "歌曲", "首歌", "放歌", "听歌")):
        q = t
        for w in ("播放", "放一首", "放首", "来一首", "来首", "我想听", "想听", "放点", "听点", "放"):
            if w in q:
                q = q.split(w, 1)[1]
                break
        q = _re.sub(r"[。！？!?，,、~～\s]+$", "", q)
        q = _re.sub(r"(的歌|音乐|歌曲|歌儿|首歌|歌|吧|呗|呀|啊)$", "", q).strip()
        return q

    # 常规动词匹配
    for w in ("播放", "放一首", "放首", "放个", "来一首", "来首", "我想听", "想听一首", "想听"):
        if w in t:
            q = t.split(w, 1)[1].strip()
            q = _re.sub(r"[。！？!?，,、~～\s]+$", "", q)
            q = _re.sub(r"(的歌|音乐|歌曲|歌儿|吧|呗|呀|啊)$", "", q).strip()
            return q

    # 识别容易把「放首」听成「放肆/放四/放个」，兜一层
    m = _re.match(r"^(?:放肆|放四|放似|放个|放歌)(.+)$", t)
    if m:
        q = _re.sub(r"[。！？!?，,、~～\s]+$", "", m.group(1)).strip()
        if q:
            return q
    return None


_ACK_CACHE = {}


async def _audio_lock_for(conn):
    """每连接一把音频锁，保证同一时刻只有一段语音在播。"""
    import asyncio as _aio

    lock = getattr(conn, "_audio_lock", None)
    if lock is None:
        lock = _aio.Lock()
        try:
            conn._audio_lock = lock
        except Exception:
            pass
    return lock


async def _interrupt_speaking(conn):
    """彻底停掉上一段语音（LLM/TTS 队列 + 播放线程），杜绝两段音频叠加。"""
    try:
        from core.handle.sendAudioHandle import send_tts_message

        # 1) 打断位：让正在跑的 LLM/TTS 循环立刻退出
        conn.client_abort = True
        try:
            conn.clear_queues()
        except Exception:
            pass

        # 2) 停播放线程（真正掐断正在输出的音频）
        try:
            conn.tts.stop()
        except Exception:
            pass

        # 3) 通知设备停止播放
        await send_tts_message(conn, "stop")
        conn.client_is_speaking = False
        try:
            conn.clearSpeakStatus()
        except Exception:
            pass

        # 4) 等上一段彻底收尾，再开口
        await asyncio.sleep(0.25)
        conn.client_abort = False
    except Exception:
        pass


async def _speak_ack(conn, text: str = "好，这就放给你听。"):
    """用 EdgeTTS 合成一句短回应并播放；串行执行，避免与其它语音重叠。"""
    lock = await _audio_lock_for(conn)
    async with lock:
        await _speak_ack_locked(conn, text)


async def _speak_ack_locked(conn, text: str = "好，这就放给你听。"):
    try:
        import edge_tts

        from core.handle.sendAudioHandle import sendAudioMessage
        from core.providers.tts.dto.dto import SentenceType
        from core.utils.util import audio_to_data

        voice = "zh-CN-XiaoxiaoNeural"
        try:
            from core.utils.voice_settings import load as _load_rt
            voice = (_load_rt().get("voice") or voice)
        except Exception:
            pass

        key = text + voice
        path = _ACK_CACHE.get(key)
        if not path:
            import tempfile

            p = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            p.close()
            comm = edge_tts.Communicate(text, voice=voice)
            audio = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            with open(p.name, "wb") as f:
                f.write(audio)
            path = p.name
            _ACK_CACHE[key] = path

        # pydub 需要 ffprobe，环境里只有 ffmpeg：先转成 wav 再解码
        import subprocess as _sp

        wav_path = path + ".wav"
        try:
            import imageio_ffmpeg as _iio
            _ff = _iio.get_ffmpeg_exe()
        except Exception:
            _ff = "ffmpeg"
        _p = _sp.run([_ff, "-v", "quiet", "-y", "-i", path,
                      "-ar", "24000", "-ac", "1", "-acodec", "pcm_s16le", wav_path],
                     capture_output=True, timeout=30)
        src = wav_path if _p.returncode == 0 else path
        packets, _ = audio_to_data(src)
        if not packets:
            raise ValueError("合成结果为空")

        # 先打断正在播的内容，再进入本段播放
        await _interrupt_speaking(conn)

        from core.handle.sendAudioHandle import send_tts_message

        await send_tts_message(conn, "start")
        conn.client_abort = False

        # 分批匀速推送（一次塞整段设备会丢帧）
        await sendAudioMessage(conn, SentenceType.FIRST, packets[:2], text)
        await asyncio.sleep(0.03)
        i = 2
        while i < len(packets):
            if getattr(conn, "client_abort", False):
                break
            await sendAudioMessage(conn, SentenceType.MIDDLE, packets[i:i + 1], None)
            i += 1
            await asyncio.sleep(0.05)
        await sendAudioMessage(conn, SentenceType.LAST, [], None)

        # 关键：播完必须发 tts stop，设备才会回到聆听状态
        await send_tts_message(conn, "stop")
        try:
            conn.client_is_speaking = False
            conn.clearSpeakStatus()
            # 关键：清掉唤醒保护位，否则后续说话会被 VAD 忽略（听不进去）
            conn.just_woken_up = False
            conn.client_abort = False
            try:
                conn.asr_audio.clear()
            except Exception:
                pass
        except Exception:
            pass
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"回应播报失败: {e}")


# ---------------- 音乐能力：点歌 / 推荐 / 查询 / 停止 ----------------
_STOP_WORDS = ("别放了", "停止播放", "停一下", "关掉音乐", "关音乐", "暂停", "别唱了", "安静")
_LIST_WORDS = ("有什么歌", "有哪些歌", "能听什么", "歌单", "都有什么歌")
_REC_WORDS = ("推荐一首", "推荐首歌", "随便放", "来点音乐", "放点音乐", "随机播放",
              "随便来首", "有什么好听", "放首歌", "听点歌", "放首歌", "放音乐", "听歌",
              "想听歌", "放首曲子", "来首歌", "放个歌", "唱首歌", "来一段音乐", "播放音乐")


async def _ensure_conn_for_play(conn, timeout=8.0):
    """点歌前确认连接还活着（设备播完会断开）。"""
    try:
        await conn.websocket.send('{"type":"ping"}')
    except Exception:
        return False
    return True


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


import os as _os_kb

_KB_URL = _os_kb.getenv("KB_URL", "http://127.0.0.1:8077").rstrip("/")
_KB_WORDS = ("知识库", "课本", "教材", "课文", "书里", "第几单元", "这个知识点",
             "资料里", "文档里", "讲过", "学过")


async def _handle_kb_cmd(conn, text: str) -> bool:
    """知识库类问题：检索后直接播报要点（不经过大模型，快且不编）。"""
    import httpx as _hx

    t = (text or "").strip()
    if not t or not any(w in t for w in _KB_WORDS):
        return False

    query = t
    for w in ("知识库", "帮我查", "查一下", "查查", "请", "一下"):
        query = query.replace(w, " ")
    query = " ".join(query.split()) or t

    hits = []
    try:
        with _hx.Client(timeout=8.0) as c:
            r = c.post(_KB_URL + "/kb/search", json={"query": query, "top_k": 3})
            hits = (r.json() or {}).get("hits") or []
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"知识库检索失败: {e}")
        return False

    if not hits:
        await _speak_ack(conn, "这个我知识库里还没有资料，你可以先在控制台的知"
                              "识库页面把课本内容加进去。")
        return True

    parts = []
    for h in hits[:3]:
        txt = (h.get("text") or h.get("content") or "").strip().replace("\n", " ")
        if txt:
            parts.append(txt[:120])
    if not parts:
        return False

    say = "我在资料里找到这些：" + "；".join(parts) + "。"
    if len(say) > 320:
        say = say[:320] + "。"
    await _speak_ack(conn, say)
    conn.logger.bind(tag=TAG).info(f"知识库回答 {len(hits)} 条命中")
    return True


def _weather_from_zone(city: str) -> str | None:
    """借专区查天气（专区里已带中国天气网兜底，open-meteo 挂了也能答）。"""
    try:
        import os as _os
        import httpx as _httpx

        base = (_os.getenv("ZONE_URL") or "http://127.0.0.1:8013").rstrip("/")
        with _httpx.Client(timeout=12.0) as c:
            r = c.post(base + "/api/v1/chat",
                       json={"message": f"{city}天气怎么样", "max_tokens": 80})
        if r.status_code != 200:
            return None
        d = r.json()
        say = (d.get("reply") or "").strip()
        # 只认专区的「快问快答」结果，避免把闲聊当成天气播报
        if say and str(d.get("model") or "").startswith("fast-weather"):
            return say
    except Exception:
        return None
    return None


async def _handle_query_cmd(conn, text: str) -> bool:
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

    # 让设备显示用户说的话（否则屏幕上没有内容）
    try:
        from core.handle.sendAudioHandle import send_stt_message
        await send_stt_message(conn, t)
    except Exception:
        pass

    WEATHER_CN = {
        0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "有雾", 48: "有雾",
        51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨", 61: "小雨", 63: "中雨",
        65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨",
        81: "强阵雨", 82: "暴雨", 95: "雷阵雨", 96: "雷阵雨伴冰雹",
    }

    if is_weather:
        city = _extract_city(t, "东莞")
        _cached = _cache_get("weather:" + city)
        if _cached:
            await _speak_ack(conn, _cached)
            return True
        city, lat, lon = _geocode_city(city)
        try:
            with _httpx.Client(timeout=5.0) as c:
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
            _cache_put("weather:" + city, say)
        except Exception as _e:
            conn.logger.bind(tag=TAG).warning(
                f"天气查询失败: {type(_e).__name__}: {_e}"
            )
            # open-meteo 挂了就借专区（专区里已带中国天气网兜底）
            say = _weather_from_zone(city) or "抱歉，天气暂时查不到，等一下再问我一次好吗。"
            if say.startswith(city):
                _cache_put("weather:" + city, say)
        await _speak_ack(conn, say)
        return True

    # 新闻
    try:
        with _httpx.Client(timeout=12.0, follow_redirects=True) as c:
            r = c.get("https://www.chinanews.com.cn/rss/scroll-news.xml")
            xml = r.text
        titles = _re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", xml)
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



_saved_actions_cache = {"at": 0.0, "data": {}}


async def _get_saved_actions(base: str, token: str) -> dict:
    """取控制台保存的自定义动作（60 秒缓存）。"""
    import time as _t

    import httpx as _hx

    now = _t.time()
    if now - _saved_actions_cache["at"] < 60 and _saved_actions_cache["data"]:
        return _saved_actions_cache["data"]
    try:
        with _hx.Client(timeout=6.0) as c:
            data = c.get(base + "/api/hardware/actions",
                         headers={"X-Hardware-Token": token}).json().get("actions") or {}
        _saved_actions_cache["at"] = now
        _saved_actions_cache["data"] = data
        return data
    except Exception:
        return _saved_actions_cache["data"]


async def _apply_pose(conn, angles: str) -> bool:
    """把 "90,50,90,121" 逐路写进舵机（MCP 直连）。"""
    import json as _json

    from core.providers.tools.device_mcp import call_mcp_tool

    try:
        parts = [int(x) for x in str(angles).replace(" ", "").split(",") if x.strip() != ""]
    except Exception:
        return False
    if len(parts) < 4:
        return False

    ok = False
    for i, ang in enumerate(parts[:4]):
        try:
            await call_mcp_tool(conn, conn.mcp_client, "self.set_servo",
                                _json.dumps({"servo": i, "angle": ang}), timeout=3)
            ok = True
        except Exception:
            pass
    return ok


async def _handle_device_cmd(conn, text: str) -> bool:
    """灯珠 / 灯光秀 / 动作：MCP 直连优先，执行完立刻回到聆听（不播报）。"""
    import json as _json
    import os as _os

    import httpx as _httpx

    t = (text or "").strip()
    if not t or len(t) > 40:
        return False

    base = _os.getenv("CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")
    token = ""

    LED_COLORS = {
        "红": "red", "绿": "green", "蓝": "blue", "黄": "yellow",
        "紫": "purple", "青": "cyan", "粉": "pink", "橙": "orange", "白": "white",
    }

    kind = action = None          # kind: action / pose / led / effect
    value = ""

    # ---------- 灯 ----------
    if any(k in t for k in ("灯", "灯珠", "发光")):
        if any(k in t for k in ("灯光秀", "彩虹", "彩灯", "跑马", "灯效")):
            kind, value = "effect", "rainbow"
        elif "呼吸" in t:
            kind, value = "effect", "breathing"
        elif "闪" in t:
            kind, value = "effect", "blink"
        elif "流水" in t:
            kind, value = "effect", "chase"
        elif any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            kind, value = "led", "off"
        else:
            for kw, name in LED_COLORS.items():
                if kw in t:
                    kind, value = "led", name
                    break
            if kind is None:
                kind, value = "led", "warm"

    # ---------- 动作 ----------
    if kind is None:
        actions = {
            "坐下": "sit", "坐": "sit",
            "趴下": "lie", "趴": "lie",
            "跳舞": "dance",
            "站起来": "stand", "起身": "stand",
            "前进": "walk", "往前走": "walk",
            "后退": "back", "往后退": "back",
            "左转": "left", "右转": "right",
            "摇尾巴": "wag", "摇摇头": "shake",
            "停下": "stop",
            # 服务端手势（固件无预设，走 gestures.py 逐帧下发）
            "握个手": "handshake", "握握手": "handshake", "握手": "handshake",
            "手给我": "handshake",
            "伸个懒腰": "stretch", "伸懒腰": "stretch",
            "转个圈": "spin", "转一圈": "spin", "转圈": "spin",
            "开心一点": "happy", "高兴一点": "happy", "撒个娇": "happy",
        }
        for word, act in actions.items():
            if word in t:
                kind, action = "action", act
                break

    if kind is None:
        return False

    # ---------- 1) MCP 直连（最快） ----------
    done = False

    # 服务端手势（握手/开心/伸懒腰/转圈）：固件没有预设，逐帧 set_pose
    if kind == "action":
        try:
            from core.utils import gestures as _gestures

            if _gestures.is_gesture(action):
                res = await _gestures.play(conn, action)
                done = bool(res.get("ok"))
                if done:
                    conn.logger.bind(tag=TAG).info(
                        f"手势 {action} 完成：{res.get('frames')} 帧"
                    )
                else:
                    conn.logger.bind(tag=TAG).warning(
                        f"手势 {action} 失败：{res.get('error')}"
                    )
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"手势执行异常：{e}")

    try:
        from core.providers.tools.device_mcp import call_mcp_tool

        if kind == "action" and not done:
            # 严格按网页保存的姿态执行
            saved = await _get_saved_actions(base, token)
            angles = saved.get(action) if saved else None
            if angles:
                # 用控制台心跳的 pose 指令：固件一次 MoveAll 平滑过渡，避免逐路设定造成的抖动
                try:
                    import httpx as _hx2

                    with _hx2.Client(timeout=6.0) as _c:
                        devs = _c.get(base + "/api/hardware/devices",
                                      headers={"X-Hardware-Token": token}).json().get("devices") or []
                        if devs:
                            _c.post(f"{base}/api/hardware/devices/{devs[0]['id']}/commands",
                                    headers={"X-Hardware-Token": token},
                                    json={"type": "pose", "params": {"value": angles}})
                            done = True
                            conn.logger.bind(tag=TAG).info(f"动作 {action} 使用自定义姿态 {angles}（pose 指令）")
                except Exception as e:
                    conn.logger.bind(tag=TAG).warning(f"pose 下发失败，改用逐路设定: {e}")
            if not done:
                await call_mcp_tool(conn, conn.mcp_client, "self.dog_action",
                                    _json.dumps({"action": action}), timeout=4)
                conn.logger.bind(tag=TAG).info(f"动作 {action} 使用固件默认")
                done = True
        elif kind == "led":
            await call_mcp_tool(conn, conn.mcp_client, "self.set_led",
                                _json.dumps({"color": value}), timeout=4)
            done = True
        elif kind == "effect":
            await call_mcp_tool(conn, conn.mcp_client, "self.led_effect",
                                _json.dumps({"effect": value}), timeout=4)
            done = True
    except Exception:
        done = False

    # ---------- 2) 失败则走控制台心跳队列（自定义姿态也在这里） ----------
    if not done:
        try:
            with _httpx.Client(timeout=8.0) as c:
                devs = c.get(base + "/api/hardware/devices",
                             headers={"X-Hardware-Token": token}).json().get("devices") or []
                if devs:
                    did = devs[0]["id"]
                    if kind == "action":
                        try:
                            saved = c.get(base + "/api/hardware/actions",
                                          headers={"X-Hardware-Token": token}).json().get("actions") or {}
                            angles = saved.get(action)
                        except Exception:
                            angles = None
                        if angles:
                            c.post(f"{base}/api/hardware/devices/{did}/commands",
                                   headers={"X-Hardware-Token": token},
                                   json={"type": "pose", "params": {"value": angles}})
                        else:
                            c.post(f"{base}/api/hardware/devices/{did}/commands",
                                   headers={"X-Hardware-Token": token},
                                   json={"type": "action", "params": {"value": action}})
                    elif kind == "led":
                        rgb = {"red": "255,0,0", "green": "0,200,0", "blue": "0,0,255",
                               "yellow": "255,200,0", "purple": "180,0,255",
                               "cyan": "0,220,200", "pink": "255,80,160",
                               "orange": "255,120,0", "white": "255,255,255",
                               "off": "0,0,0", "warm": "255,200,0"}.get(value, "255,200,0")
                        c.post(f"{base}/api/hardware/devices/{did}/commands",
                               headers={"X-Hardware-Token": token},
                               json={"type": "led", "params": {"value": rgb}})
                    else:
                        c.post(f"{base}/api/hardware/devices/{did}/commands",
                               headers={"X-Hardware-Token": token},
                               json={"type": "led", "params": {"value": value}})
        except Exception:
            pass

    # ---------- 3) 收尾：先回到聆听，再回一句确认 ----------
    try:
        from core.handle.sendAudioHandle import send_tts_message

        # 直接发 stop：设备处于 speaking 时会切回聆听；处于聆听时无副作用
        conn.client_abort = False
        await send_tts_message(conn, "stop")
        conn.client_is_speaking = False
        try:
            conn.clearSpeakStatus()
        except Exception:
            pass

        # 动作做完必须有反馈。这里直接播固定短句，不再走大模型——
        # 之前这条路径只发 stop 不说话，体感就是「狗动了但没回应」。
        reply = None
        if kind == "action":
            try:
                from core.utils.console_actions import ACTION_REPLIES

                reply = ACTION_REPLIES.get(action)
            except Exception:
                reply = None
        elif kind in ("led", "effect"):
            reply = "好，灯换好了。"
        if reply and getattr(conn, "tts", None) is not None:
            from core.providers.tts.dto.dto import ContentType

            conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=reply)
    except Exception:
        pass

    return True



async def _handle_music_cmd(conn, text: str) -> bool:
    """处理音乐类指令；已处理返回 True。"""
    if not text:
        return False
    t = text.strip()

    # 1) 停止
    if any(w in t for w in _STOP_WORDS):
        conn.client_abort = True
        conn.logger.bind(tag=TAG).info("音乐：收到停止指令")
        try:
            await _speak_ack(conn, "好，停了。")
        except Exception:
            pass
        return True

    # 2) 查询可点歌曲
    if any(w in t for w in _LIST_WORDS):
        conn.logger.bind(tag=TAG).info("音乐：查询可点歌曲")
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get("http://127.0.0.1:8080/api/music/search",
                                params={"q": "热门", "limit": 3})
                songs = (r.json() or {}).get("songs") or []
            names = "、".join(str(s.get("title") or "") for s in songs[:3])
            msg = f"现在可以点这些：{names}。想听哪首？" if names else "暂时没查到能放的歌。"
            await _speak_ack(conn, msg)
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"查询歌曲失败: {e}")
        return True

    # 3) 推荐 / 随机
    if any(w in t for w in _REC_WORDS) and not any(w in t for w in ("播放", "放一", "放首", "来一首")):
        conn.logger.bind(tag=TAG).info("音乐：推荐并播放")
        try:
            import httpx

            await _speak_ack(conn, "好，给你放首轻音乐。")
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post("http://127.0.0.1:8080/api/music/play_device",
                                 json={"query": "轻音乐"})
                d = r.json()
            if not d.get("ok"):
                conn.logger.bind(tag=TAG).warning(f"推荐播放未成功: {d}")
                await _speak_ack(conn, "这会儿放不出来，等一下再试试。")
            # 无论成功与否都算已处理，避免落到模型闲聊
            return True
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"推荐播放失败: {e}")
            await _speak_ack(conn, "这会儿放不出来，等一下再试试。")
            return True

    # 4) 点播指定歌曲（沿用原逻辑）
    return False


async def _try_play_music(conn, text: str) -> bool:
    """命中点歌意图且播放成功时返回 True；失败返回 False 交给正常对话。"""
    q = _parse_music_query(text)
    if q is None:
        return False
    conn.logger.bind(tag=TAG).info(f"识别到点歌意图：{q or '（随机）'}")
    if not await _ensure_conn_for_play(conn):
        conn.logger.bind(tag=TAG).warning("点歌前连接已断开，跳过")
        return False
    try:
        import httpx

        # 先说一句，掩盖搜索/缓冲的等待
        await _speak_ack(conn)

        base = "http://127.0.0.1:8080"
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{base}/api/music/play_device",
                             json={"query": q or "轻音乐"})
            d = r.json()
        ok = bool(d.get("ok"))
        song = ((d.get("song") or {}).get("name") or q or "音乐")
        conn.logger.bind(tag=TAG).info(f"点歌结果：ok={ok} song={song} raw={str(d)[:120]}")
        if not ok:
            conn.logger.bind(tag=TAG).warning("点歌失败")
            await _speak_ack(conn, "没找到这首，换一首试试？")
        return True
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"点歌异常，回退正常对话: {e}")
        return False


_speak_guard_task = {}


async def _speak_stuck_guard(conn):
    """检查「说话状态卡死」：说话标记为真，但既没有新语音、也早就不再推音频。

    之前只看 25 秒有没有新语音，导致两种坏情况：
      - 卡住后要等 25 秒才复位，用户体感就是「一直聆听中、听不进去」；
      - 长故事播报时用户不说话，反而可能被误复位。
    现在同时要求「最近 8 秒没推过音频」，长播报期间 last_activity_time 一直在刷新，
    不会被误判；真卡住时 8~13 秒就能回到可收音状态。
    """
    import time as _time

    last_seen = getattr(conn, "client_have_voice", False)
    idle = 0
    speaking_since = None
    while True:
        await asyncio.sleep(2)
        try:
            speaking = bool(getattr(conn, "client_is_speaking", False))
            have_voice = bool(getattr(conn, "client_have_voice", False))
            if speaking and speaking_since is None:
                speaking_since = _time.time()
            elif not speaking:
                speaking_since = None
            if have_voice != last_seen:
                last_seen = have_voice
                idle = 0
                continue
            idle += 2
            now_ms = _time.time() * 1000
            last_send = float(getattr(conn, "last_activity_time", 0) or 0)
            quiet_ms = now_ms - last_send if last_send else 1e9
            # 说话状态持续 ≥15 秒（躲开「模型思考中还没出声」的空窗）
            # 且 ≥8 秒没有新语音、≥8 秒没推音频 → 判定卡死
            speak_age = (_time.time() - speaking_since) if speaking_since else 0

            # 关键：TTS 还有待合成的文本 / 待播的音频时，绝不能复位。
            # 长回复的首段音频可能要十几秒才合成出来，复位会把 stop 插到
            # 正式播报之前，设备收到 stop 就再也不出声了（表现为「没声音」）。
            tts_busy = False
            tts = getattr(conn, "tts", None)
            if tts is not None:
                try:
                    tts_busy = not (
                        tts.tts_text_queue.empty() and tts.tts_audio_queue.empty()
                    )
                except Exception:
                    tts_busy = False

            # 兜底：真遇到 TTS 队列卡死（>90 秒），再强制复位，否则会永远卡住
            hard_stuck = speaking and speak_age >= 90
            if (
                speaking
                and speak_age >= 15
                and idle >= 8
                and quiet_ms >= 8000
                and (not tts_busy or hard_stuck)
            ):
                from core.handle.sendAudioHandle import send_tts_message

                conn.logger.bind(tag=TAG).warning(
                    f"检测到说话状态卡死，强制复位（说话 {speak_age:.0f}s / "
                    f"静默 {quiet_ms/1000:.1f}s）"
                )
                conn.client_is_speaking = False
                conn.client_abort = False
                conn.just_woken_up = False
                try:
                    conn.clearSpeakStatus()
                except Exception:
                    pass
                try:
                    conn.asr_audio.clear()
                except Exception:
                    pass
                await send_tts_message(conn, "stop")
                idle = 0
        except asyncio.CancelledError:
            return
        except Exception:
            pass


def _ensure_speak_guard(conn):
    task = _speak_guard_task.get(id(conn))
    if task is None or task.done():
        import asyncio as _aio

        _speak_guard_task[id(conn)] = _aio.create_task(_speak_stuck_guard(conn))


async def handleAudioMessage(conn, audio):
    # 阶段零打点：T0 = 最后一帧上行音频的到达时间（每帧刷新）
    try:
        from core.utils import latency as _lat

        _lat.frame(conn)
    except Exception:
        pass
    try:
        _ensure_speak_guard(conn)
    except Exception:
        pass
    # 当前片段是否有人说话
    have_voice = conn.vad.is_vad(conn, audio)
    # 如果设备刚刚被唤醒，短暂忽略VAD检测
    if have_voice and hasattr(conn, "just_woken_up") and conn.just_woken_up:
        have_voice = False
        # 设置一个短暂延迟后恢复VAD检测
        conn.asr_audio.clear()
        if not hasattr(conn, "vad_resume_task") or conn.vad_resume_task.done():
            conn.vad_resume_task = asyncio.create_task(resume_vad_detection(conn))
        return

    if have_voice:
        if conn.client_is_speaking:
            await handleAbortMessage(conn)
    # 设备长时间空闲检测，用于say goodbye
    await no_voice_close_connect(conn, have_voice)
    # 接收音频
    await conn.asr.receive_audio(conn, audio, have_voice)


async def resume_vad_detection(conn):
    # 等待2秒后恢复VAD检测
    await asyncio.sleep(1)
    conn.just_woken_up = False


async def startToChat(conn, text):
    # 阶段零打点：T2 = ASR 出文本（T1 由设备 stop/detect 消息标记，这里不要再覆盖 T1，
    # 否则 asr_ms 会恒为 0）
    try:
        from core.utils import latency as _lat

        _lat.mark(conn, "t2", text=(text or "")[:40])
    except Exception:
        pass
    if conn.need_bind:
        await check_bind_device(conn)
        return

    # 如果当日的输出字数大于限定的字数
    if conn.max_output_size > 0:
        if check_device_output_limit(
            conn.headers.get("device-id"), conn.max_output_size
        ):
            await max_out_size(conn)
            return
    if conn.client_is_speaking:
        await handleAbortMessage(conn)

    # 关键词兜底：识别到「趴下」「左转」这类动作，直接走设备 MCP，
    # 不依赖大模型是否愿意调用工具。没命中会正常往下走。
    if await try_handle_voice_command(conn, text):
        return

    # 天气/新闻直通：优先于意图处理，由我们自己播报（整句、不分段）
    try:
        if await _handle_query_cmd(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"查询直通异常: {e}")

    # 知识库直通
    try:
        if await _handle_kb_cmd(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"知识库直通异常: {e}")

    # 首先进行意图分析
    intent_handled = await handle_user_intent(conn, text)

    if intent_handled:
        # 如果意图已被处理，不再进行聊天
        return

    # 意图未被处理，继续常规聊天流程
    await send_stt_message(conn, text)
    # 设备指令 / 点歌直通：不经过大模型
    try:
        if await _handle_device_cmd(conn, text):
            return
        if await _handle_music_cmd(conn, text):
            return
        if await _try_play_music(conn, text):
            return
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"指令直通异常: {e}")

    conn.executor.submit(conn.chat, text)


async def no_voice_close_connect(conn, have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # 只有在已经初始化过时间戳的情况下才进行超时检查
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
            conn.client_abort = False
            end_prompt = conn.config.get("end_prompt", {})
            if end_prompt and end_prompt.get("enable", True) is False:
                conn.logger.bind(tag=TAG).info("结束对话，无需发送结束提示语")
                await conn.close()
                return
            prompt = end_prompt.get("prompt")
            if not prompt:
                prompt = "请你以```时间过得真快```未来头，用富有感情、依依不舍的话来结束这场对话吧。！"
            await startToChat(conn, prompt)


async def max_out_size(conn):
    text = "不好意思，我现在有点事情要忙，明天这个时候我们再聊，约好了哦！明天不见不散，拜拜！"
    await send_stt_message(conn, text)
    file_path = "config/assets/max_output_size.wav"
    opus_packets, _ = audio_to_data(file_path)
    conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
    conn.close_after_chat = True


async def check_bind_device(conn):
    if conn.bind_code:
        # 确保bind_code是6位数字
        if len(conn.bind_code) != 6:
            conn.logger.bind(tag=TAG).error(f"无效的绑定码格式: {conn.bind_code}")
            text = "绑定码格式错误，请检查配置。"
            await send_stt_message(conn, text)
            return

        text = f"请登录控制面板，输入{conn.bind_code}，绑定设备。"
        await send_stt_message(conn, text)

        # 播放提示音
        music_path = "config/assets/bind_code.wav"
        opus_packets, _ = audio_to_data(music_path)
        conn.tts.tts_audio_queue.put((SentenceType.FIRST, opus_packets, text))

        # 逐个播放数字
        for i in range(6):  # 确保只播放6位数字
            try:
                digit = conn.bind_code[i]
                num_path = f"config/assets/bind_code/{digit}.wav"
                num_packets, _ = audio_to_data(num_path)
                conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, num_packets, None))
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"播放数字音频失败: {e}")
                continue
        conn.tts.tts_audio_queue.put((SentenceType.LAST, [], None))
    else:
        text = f"没有找到该设备的版本信息，请正确配置 OTA地址，然后重新编译固件。"
        await send_stt_message(conn, text)
        music_path = "config/assets/bind_not_found.wav"
        opus_packets, _ = audio_to_data(music_path)
        conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
