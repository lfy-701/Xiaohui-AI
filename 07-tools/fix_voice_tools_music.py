"""强制工具通道 + 语音点歌连接保障。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 1) 天气/新闻/搜索/动作 永久走工具通道 ----------
F = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\providers\llm\openai\openai.py")
t = F.read_text(encoding="utf-8")

if "STRICT_TOOL_HINTS" not in t:
    helper = '''
# 这些意图必须走工具通道：宁可慢 2 秒，也不能让模型编造
STRICT_TOOL_HINTS = (
    "天气", "气温", "温度", "下雨", "下雪", "冷不冷", "热不热", "穿什么",
    "空气质量", "预报", "台风", "暴雨",
    "新闻", "头条", "热搜", "时事", "最近发生",
    "搜索", "搜一下", "查一下", "查查", "限行", "路况", "多少钱", "汇率",
)

'''
    idx = t.find("_TOOL_HINTS = (")
    if idx > 0:
        t = t[:idx] + helper.strip() + "\n\n" + t[idx:]

# _tool_mode_for：命中严格词一律走工具
old = '''def _tool_mode_for(dialogue):
    """需要工具/实时信息时返回 None（走完整通道），闲聊返回 "off"。"""
    txt = _last_user_text(dialogue)
    if not txt:
        return "off"
    return None if any(k in txt for k in _TOOL_HINTS) else "off"'''

new = '''def _tool_mode_for(dialogue):
    """需要工具/实时信息时返回 None（走完整通道），闲聊返回 "off"。"""
    txt = _last_user_text(dialogue)
    if not txt:
        return "off"
    if any(k in txt for k in STRICT_TOOL_HINTS):
        return None
    return None if any(k in txt for k in _TOOL_HINTS) else "off"'''

if old in t:
    t = t.replace(old, new, 1)
    F.write_text(t, encoding="utf-8")
    ast.parse(t)
    print("语音：严格工具通道已启用")

# ---------- 2) 语音点歌：先确保连接 ----------
R = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
r = R.read_text(encoding="utf-8")

if "_ensure_conn_for_play" not in r:
    helper2 = '''
async def _ensure_conn_for_play(conn, timeout=8.0):
    """点歌前确认连接还活着（设备播完会断开）。"""
    try:
        await conn.websocket.send('{"type":"ping"}')
    except Exception:
        return False
    return True

'''
    idx2 = r.find("async def _handle_music_cmd")
    if idx2 > 0:
        r = r[:idx2] + helper2.strip() + "\n\n\n" + r[idx2:]

    # 点播前调用
    old2 = '''    conn.logger.bind(tag=TAG).info(f"识别到点歌意图：{q or '（随机）'}")'''
    new2 = '''    conn.logger.bind(tag=TAG).info(f"识别到点歌意图：{q or '（随机）'}")
    if not await _ensure_conn_for_play(conn):
        conn.logger.bind(tag=TAG).warning("点歌前连接已断开，跳过")
        return False'''
    if old2 in r:
        r = r.replace(old2, new2, 1)
        R.write_text(r, encoding="utf-8")
        ast.parse(r)
        print("语音：点歌连接检查已加")
    else:
        print("⚠ 点歌意图日志行未匹配")
