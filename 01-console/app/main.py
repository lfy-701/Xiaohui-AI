"""小慧控制台：智能体 / 设备 / 日志 / 记忆的统一后台。"""
from __future__ import annotations

import json
import os
import time
import uuid
import subprocess
import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Response, File, HTTPException, Form, Request, UploadFile, Body
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db as store
from . import auth, llm

STATIC = Path(__file__).resolve().parent.parent / "static"
KB_URL = os.getenv("KB_URL", "")          # 例如 http://127.0.0.1:8077
LLM_URL = os.getenv("LLM_CHAT_URL", "")   # 模型服务地址，用于「试聊」
WS_URL = os.getenv("WS_URL", "")
if not WS_URL:
    # 环境变量缺失时读文件兜底，避免下发 127.0.0.1 让设备连自己
    try:
        _f = Path(__file__).resolve().parent.parent / "data" / "ws_url.txt"
        if _f.exists():
            WS_URL = _f.read_text(encoding="utf-8").strip()
    except Exception:
        pass
WS_TOKEN = ""
FIRMWARE_DIR = Path(os.getenv("FIRMWARE_DIR", "./data/firmware"))
FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)

# 设备侧共享密钥：必须由环境变量提供，代码里不留默认值
DEVICE_TOKEN = ""

# 模型服务（含 MCP 管理接口）地址：由环境变量提供，仓库内不留真实内网地址
MCP_BASE = os.getenv("MCP_BASE_URL", "").rstrip("/")
# 远程写操作令牌：只存在后端，绝不下发到浏览器
MCP_ADMIN_TOKEN = ""

# 小慧音乐 MCP 服务（我们自己起的，带 REST 兼容层）
MUSIC_BASE = os.getenv("MUSIC_BASE_URL", "http://127.0.0.1:8102").rstrip("/")
# 语音服务 HTTP 口（控制台动作/状态代理用）
VOICE_HTTP_BASE = os.getenv("VOICE_HTTP_BASE", "http://127.0.0.1:8003").rstrip("/")
# 本地曲库目录（放整首歌文件的文件夹）
MUSIC_DIR = Path(os.getenv("MUSIC_LIBRARY_DIR", "./data/music")).resolve()
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="小慧控制台", version="1.0.0")

from app.training_center import router as training_router
app.include_router(training_router)


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    """设了 CONSOLE_PASSWORD 才拦；否则开发模式全放行。"""
    path = request.url.path
    if path in ("/login", "/logout", "/favicon.ico") or path.startswith("/static"):
        return await call_next(request)
    # 设备侧接口：不走登录，改用共享 token 鉴权
    if path in ("/api/devices/register", "/api/devices/heartbeat", "/ota/", "/ota"):
        return await call_next(request)
    # 设备拉音频不需要登录（纯转发，无敏感数据）
    if path.startswith("/audio"):
        return await call_next(request)
    # 训练侧硬件接口：用 X-Hardware-Token 鉴权，不走登录态
    if path.startswith("/api/hardware/"):
        return await call_next(request)
    if path.startswith("/firmware/"):
        return await call_next(request)
    # 本机内部调用（语音服务推歌等）放行
    try:
        if request.client and request.client.host in ("127.0.0.1", "::1") and path.startswith("/api/music/"):
            return await call_next(request)
    except Exception:
        pass
    if auth.is_authed(request):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "未登录"}, status_code=401)
    return auth.login_page()


@app.get("/login")
def login_get():
    return auth.login_page()


@app.post("/login")
async def login_post(request: Request):
    form = await request.form()
    if auth.enabled() and hmac_compare(form.get("password", ""), auth.PASSWORD):
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(auth.COOKIE, auth._token(), max_age=auth._MAX_AGE,
                        httponly=True, samesite="lax")
        return resp
    return auth.login_page("密码不对，请重试")


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login")
    resp.delete_cookie(auth.COOKIE)
    return resp


def hmac_compare(a: str, b: str) -> bool:
    import hmac as _h
    return _h.compare_digest(str(a), str(b))


@app.on_event("startup")
def _startup() -> None:
    store.init_db()
    if not store.list_agents():
        a = store.create_agent({
            "name": "小慧",
            "avatar": "🐶",
            "persona": "你叫小慧，是主人身边最亲近的伙伴。说话温柔自然，像熟人聊天一样，"
                       "不客套、不说「作为一个AI」这类话。回答简短，两三句说完，"
                       "偶尔关心一下主人今天过得怎么样。",
            "wake_word": "你好小智",
        })
        store.add_log("system", "已创建默认智能体：小慧", agent_id=a["id"])


# ---------------------------------------------------------------- 智能体

class AgentIn(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    persona: Optional[str] = None
    model: Optional[str] = None
    voice: Optional[str] = None
    language: Optional[str] = None
    wake_word: Optional[str] = None
    kb_enabled: Optional[bool] = None
    kb_topk: Optional[int] = None
    memory_enabled: Optional[bool] = None
    temperature: Optional[float] = None


@app.get("/api/agents")
def api_list_agents():
    return {"agents": store.list_agents()}


@app.post("/api/agents")
def api_create_agent(body: AgentIn):
    return store.create_agent(body.model_dump())


@app.get("/api/agents/{agent_id}")
def api_get_agent(agent_id: str):
    a = store.get_agent(agent_id)
    if not a:
        raise HTTPException(404, "agent not found")
    return a


@app.put("/api/agents/{agent_id}")
def api_update_agent(agent_id: str, body: AgentIn):
    # 模型为空时保留原值，避免界面误存把配置清空
    _body = body.model_dump()
    _cur = store.get_agent(agent_id)
    if not (_body.get("model") or "").strip() and _cur and _cur.get("model"):
        _body["model"] = _cur["model"]
    a = store.update_agent(agent_id, _body)
    # 记录配置变更，支持回滚
    try:
        _watched = ("persona", "model", "voice", "wake_word", "temperature",
                    "kb_enabled", "kb_topk", "memory_enabled")
        for _f in _watched:
            if _f not in _body:
                continue
            _old = (_cur or {}).get(_f)
            _new = _body.get(_f)
            if _old != _new:
                store.add_config_history(agent_id, _f,
                                         "" if _old is None else str(_old),
                                         "" if _new is None else str(_new))
    except Exception:
        pass
    # 音色 / 模型 / 角色设定 / 唤醒词 都要同步给语音服务，
    # 保存后下一次对话即生效，不需要重启服务或重新配网。
    if a.get("voice"):
        _sync_engine_voice(a["voice"])
    if a.get("model"):
        _sync_engine_model(a["model"])
    if a.get("persona"):
        _sync_engine_prompt(a["persona"])
    if a.get("wake_word"):
        _sync_engine_wakeup(a["wake_word"])
    return a


@app.delete("/api/agents/{agent_id}")
def api_delete_agent(agent_id: str):
    store.delete_agent(agent_id)
    return {"deleted": agent_id}


# ---------------------------------------------------------------- 设备

class HeartbeatIn(BaseModel):
    mac: str
    name: str = ""
    agent_id: str = ""
    firmware: str = ""
    ip: str = ""


@app.get("/api/devices")
def api_devices():
    return {"devices": store.list_devices()}


def _check_device_token(request: Request) -> None:
    if not DEVICE_TOKEN:
        # 没配置就拒绝设备接入，避免「空 token 等于不校验」的危险默认值
        raise HTTPException(503, "服务端未配置 DEVICE_TOKEN，设备接入已禁用")
    token = ""
    if not hmac_compare(token, DEVICE_TOKEN):
        raise HTTPException(401, "设备 token 不正确")


@app.post("/api/devices/register")
def api_device_register(request: Request, body: HeartbeatIn):
    """设备开机自报，返回激活码（首次）。无需登录，用 X-Device-Token 校验。"""
    _check_device_token(request)
    client_ip = request.client.host if request.client else ""
    return store.register_device(body.mac, body.firmware, body.ip or client_ip)


def _to_pinyin(text: str) -> str:
    """中文转不带声调的拼音，MultiNet 需要这种格式。"""
    try:
        from pypinyin import lazy_pinyin

        parts = lazy_pinyin((text or "").strip())
        return " ".join(p for p in parts if p.strip()).lower()
    except Exception:
        return ""


def _wake_words_for(cfg: dict) -> list:
    """给设备下发的唤醒词清单：固定保留「你好小慧」作为保底词。"""
    words = [{"pinyin": "ni hao xiao hui", "display": "你好小慧"}]
    agent = (cfg or {}).get("agent") or {}
    w = (agent.get("wake_word") or "").strip()
    if w and w != "你好小慧":
        py = _to_pinyin(w)
        if py:
            words.append({"pinyin": py, "display": w})
    return words


@app.post("/api/devices/heartbeat")
def api_heartbeat(request: Request, body: HeartbeatIn):
    """设备心跳，顺带返回自己的绑定配置。"""
    _check_device_token(request)
    client_ip = request.client.host if request.client else ""
    dev = store.register_device(body.mac, body.firmware, body.ip or client_ip)
    cfg = store.device_config(body.mac) or {}
    cfg = dict(cfg)
    # 设备据此在本地重建唤醒词命令表（运行时生效，无需重刷固件）
    cfg["wake_words"] = _wake_words_for(cfg)
    # 控制台排队的动作/表情，设备心跳时取走执行
    try:
        cfg["commands"] = store.take_commands(body.mac)
    except Exception:
        cfg["commands"] = []
    return {**dev, "config": cfg}


class BindIn(BaseModel):
    code: str
    agent_id: str


@app.post("/api/devices/bind")
def api_device_bind(body: BindIn):
    """控制台上输入 6 位激活码，把设备绑到某个智能体。"""
    dev = store.bind_device(body.code.strip(), body.agent_id)
    if not dev:
        raise HTTPException(404, "激活码不存在")
    store.add_log("system", f"设备 {dev['mac']} 已绑定智能体 {body.agent_id}", agent_id=body.agent_id)
    return dev


@app.delete("/api/devices/{device_id}")
def api_delete_device(device_id: str):
    # 必须先解绑才能删除，避免误删在线设备
    _tgt = None
    for _d in store.list_devices():
        if _d["id"] == device_id:
            _tgt = _d
            break
    if _tgt is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if _tgt.get("bound"):
        raise HTTPException(status_code=409, detail="请先解绑，再删除设备")
    store.add_log("system", "已删除设备 " + (_tgt.get("mac") or device_id))
    store.delete_device(device_id)
    return {"deleted": device_id}


@app.post("/api/devices/{device_id}/unbind")
def api_device_unbind(device_id: str):
    store.unbind_device(device_id)
    return {"unbound": device_id}


class RenameIn(BaseModel):
    name: str


@app.post("/api/devices/{device_id}/rename")
def api_device_rename(device_id: str, body: RenameIn):
    store.rename_device(device_id, body.name.strip())
    return {"renamed": device_id, "name": body.name.strip()}


# ---------------------------------------------------------------- 日志 / 记忆

@app.get("/api/logs")
def api_logs(agent_id: str = "", limit: int = 100):
    return {"logs": store.list_logs(agent_id, limit)}


@app.get("/api/agents/{agent_id}/memory")
def api_agent_memory(agent_id: str, user_id: str = "default"):
    if not KB_URL:
        return {"enabled": False, "reason": "未配置 KB_URL", "facts": []}
    try:
        with httpx.Client(timeout=5.0) as c:
            return {"enabled": True, **c.get(f"{KB_URL}/memory/{user_id}").json()}
    except Exception as e:
        return {"enabled": False, "reason": str(e), "facts": []}


class ChatIn(BaseModel):
    user_id: str = "default"
    session_id: str = "default"
    text: str = ""


@app.get("/api/agents/{agent_id}/chat/history")
def api_chat_history(agent_id: str, session_id: str = "default"):
    _msgs = [m for m in store.chat_history(session_id, 50) if str((m.get("content") if isinstance(m, dict) else "") or "").strip()]
    return {"session_id": session_id, "messages": _msgs}


@app.post("/api/agents/{agent_id}/chat/reset")
def api_chat_reset(agent_id: str, body: ChatIn):
    store.clear_chat(body.session_id)
    return {"ok": True, "session_id": body.session_id}


def _prepare_chat(agent_id: str, body: "ChatIn"):
    """组装 messages：人设 + 记忆 + 知识库 + 历史。"""
    a = store.get_agent(agent_id)
    if not a:
        raise HTTPException(404, "agent not found")

    session_id = body.session_id or "default"

    context = ""
    if KB_URL and a["memory_enabled"]:
        try:
            with httpx.Client(timeout=5.0) as c:
                context = c.get(f"{KB_URL}/memory/{body.user_id}/prompt").json().get("prompt", "")
        except Exception:
            pass

    kb_hits = []
    if KB_URL and a["kb_enabled"]:
        try:
            with httpx.Client(timeout=8.0) as c:
                kb_hits = c.post(f"{KB_URL}/kb/search",
                                 json={"query": body.text, "top_k": a["kb_topk"]}).json().get("hits", [])
        except Exception:
            pass

    # 注入当前日期时间，避免模型凭空编造「今天」
    _now = datetime.datetime.now()
    _weekday = "一二三四五六日"[_now.weekday()]
    _dt_hint = "当前时间：{}年{}月{}日 星期{} {}:{}。回答涉及日期时间时以此为准。\n".format(
        _now.year, _now.month, _now.day, _weekday,
        str(_now.hour).zfill(2), str(_now.minute).zfill(2))
    system_prompt = (_dt_hint + (a["persona"] or "") + "\n" + context
                     + ("\n【参考知识】\n" + "\n".join(h["text"] for h in kb_hits) if kb_hits else "")
                     + "\n\n【输出要求】用口语回答，最多三句话。不要分点、不要 markdown、"
                       "不要括号补充说明，不要重复用户的问题。")

    history = store.chat_history(session_id, 20)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": body.text})

    return a, session_id, messages, context, kb_hits, history


def _remember_turn(user_id: str, user_text: str, reply: str, agent_id: str) -> None:
    """把这一轮写进记忆服务，抽取用户在意的信息（名字、住址、偏好…）。"""
    if not KB_URL or not user_text.strip():
        return
    try:
        with httpx.Client(timeout=8.0) as c:
            c.post(f"{KB_URL}/memory/turn", json={
                "user_id": user_id,
                "user": user_text,
                "assistant": reply,
            })
    except Exception:
        pass


@app.post("/api/agents/{agent_id}/chat")
def api_test_chat(agent_id: str, body: ChatIn):
    """试聊（非流式）：多轮上下文 + 记忆 + 知识库。"""
    # 1) 日期/星期直接算
    try:
        _date_reply = _date_answer(str(getattr(body, 'text', '') or ''))
        if _date_reply:
            return {'reply': _date_reply, 'model': 'date',
                    'session_id': getattr(body, 'session_id', '') or ''}
    except Exception:
        pass

    # 2) 天气直接查 Open-Meteo（避免模型编温度）
    try:
        _w_reply = _weather_answer(str(getattr(body, 'text', '') or ''))
        if _w_reply:
            return {'reply': _w_reply, 'model': 'weather',
                    'session_id': getattr(body, 'session_id', '') or ''}
    except Exception:
        pass

    # 3) 设备指令直通（灯珠/动作/澄清）
    try:
        _txt = str(getattr(body, 'text', '') or '')
        _kind, _val, _say = _device_cmd_from_text(_txt)
        if _kind:
            if _push_device_cmd(_kind, _val):
                return {'reply': _say, 'model': 'device-cmd',
                        'session_id': getattr(body, 'session_id', '') or ''}
            return {'reply': '设备现在没连上，等它连上我再试。',
                    'model': 'device-cmd', 'session_id': ''}
        _short = _txt.strip()
        _greet = ('你好', '您好', '谢谢', '再见', '在吗', '小慧', '哈喽', '嗨', '早', '晚安', '嗯', '好')
        if (1 <= len(_short) <= 5 and not any(ch in _short for ch in '?？吗呢啊')
                and not any(w in _short for w in _greet)):
            return {'reply': '我没太听清，你是想让我做动作还是开灯？可以说「站起来」或「红灯」。',
                    'model': 'clarify', 'session_id': ''}
    except Exception:
        pass

    a, session_id, messages, context, kb_hits, history = _prepare_chat(agent_id, body)

    store.add_chat_message(session_id, agent_id, "user", body.text)
    store.add_log("user", body.text, agent_id)

    model = a["model"] or ""
    st = llm.status()
    if not st["online"]:
        reply = (f"[未接入模型] {st['hint']}\n"
                 f"收到：{body.text}\n"
                 f"（已取到记忆 {len(context)} 字、知识片段 {len(kb_hits)} 条、历史 {len(history)} 轮）")
    else:
        try:
            reply, used = llm.chat(model, messages)
            reply = f"{reply}\n\n—— {used}"
        except Exception as e:
            reply = f"[模型调用失败] {e}"

    store.add_chat_message(session_id, agent_id, "assistant", reply)
    store.add_log("assistant", reply, agent_id)
    _remember_turn(body.user_id, body.text, reply, agent_id)
    return {"reply": reply, "kb_hits": len(kb_hits), "context": context,
            "session_id": session_id, "turns": len(history) // 2}


@app.post("/api/agents/{agent_id}/chat/stream")
def api_chat_stream(agent_id: str, body: ChatIn):
    """试聊（SSE 流式）。事件格式：data: {"delta":"..."} … data: [DONE]"""
    a, session_id, messages, context, kb_hits, history = _prepare_chat(agent_id, body)

    store.add_chat_message(session_id, agent_id, "user", body.text)
    store.add_log("user", body.text, agent_id)
    model = a["model"] or ""

    def gen():
        acc: List[str] = []
        try:
            for piece in llm.chat_stream(model, messages):
                acc.append(piece)
                yield "data: " + json.dumps({"delta": piece}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}, ensure_ascii=False) + "\n\n"
        finally:
            full = "".join(acc)
            if full:
                store.add_chat_message(session_id, agent_id, "assistant", full)
                store.add_log("assistant", full, agent_id)
                _remember_turn(body.user_id, body.text, full, agent_id)
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/models")
def api_models():
    return llm.status()


# ---------------------------------------------------------------- 音色
# 从 Edge TTS 拉真实可用音色（不是硬编码列表），并能现场试听。

_VOICE_NAME = {
    "Xiaoxiao": "晓晓", "Xiaoyi": "晓伊", "Yunjian": "云健", "Yunxi": "云希",
    "Yunxia": "云夏", "Yunyang": "云扬", "Xiaobei": "晓北", "Xiaoni": "晓妮",
    "HiuGaai": "曉佳", "HiuMaan": "曉曼", "WanLung": "雲龍",
    "HsiaoChen": "曉臻", "HsiaoYu": "曉雨", "YunJhe": "雲哲",
    "Aria": "Aria", "Guy": "Guy", "Jenny": "Jenny", "Davis": "Davis",
    "Nanami": "七海", "Keita": "圭太", "SunHi": "善熙", "InJoon": "仁俊",
}
_GENDER_LABEL = {"Female": "女声", "Male": "男声"}

# 语种中文名 + 分组（分组用于界面归类）
_LOCALE_CN = {
    "zh-CN": ("普通话", "中文"),
    "zh-CN-liaoning": ("东北话", "中文·方言"),
    "zh-CN-shaanxi": ("陕西话", "中文·方言"),
    "zh-HK": ("粤语", "中文·方言"),
    "zh-TW": ("台湾国语", "中文·方言"),
    "en-US": ("英语（美）", "英语"),
    "en-GB": ("英语（英）", "英语"),
    "en-AU": ("英语（澳）", "英语"),
    "en-CA": ("英语（加）", "英语"),
    "en-IN": ("英语（印）", "英语"),
    "en-IE": ("英语（爱）", "英语"),
    "en-NZ": ("英语（新）", "英语"),
    "ja-JP": ("日语", "日语"),
    "ko-KR": ("韩语", "韩语"),
    "fr-FR": ("法语", "法语"),
    "fr-CA": ("法语（加）", "法语"),
    "de-DE": ("德语", "德语"),
    "es-ES": ("西班牙语", "西班牙语"),
    "es-MX": ("西班牙语（墨）", "西班牙语"),
    "it-IT": ("意大利语", "其他外语"),
    "pt-BR": ("葡萄牙语（巴）", "其他外语"),
    "pt-PT": ("葡萄牙语", "其他外语"),
    "ru-RU": ("俄语", "其他外语"),
    "ar-SA": ("阿拉伯语", "其他外语"),
    "hi-IN": ("印地语", "其他外语"),
    "th-TH": ("泰语", "其他外语"),
    "vi-VN": ("越南语", "其他外语"),
    "nl-NL": ("荷兰语", "其他外语"),
    "tr-TR": ("土耳其语", "其他外语"),
    "pl-PL": ("波兰语", "其他外语"),
    "sv-SE": ("瑞典语", "其他外语"),
    "id-ID": ("印尼语", "其他外语"),
    "ms-MY": ("马来语", "其他外语"),
}

_voice_cache: Dict[str, Any] = {"at": 0.0, "voices": []}

# 语言前缀 → 中文名（用于把 300 多个音色归到有意义的组里）
_LANG_CN = {
    "ar": "阿拉伯语", "ru": "俄语", "th": "泰语", "vi": "越南语", "id": "印尼语",
    "ms": "马来语", "nl": "荷兰语", "pl": "波兰语", "tr": "土耳其语", "sv": "瑞典语",
    "da": "丹麦语", "nb": "挪威语", "fi": "芬兰语", "cs": "捷克语", "sk": "斯洛伐克语",
    "hu": "匈牙利语", "ro": "罗马尼亚语", "el": "希腊语", "he": "希伯来语", "hi": "印地语",
    "bn": "孟加拉语", "ta": "泰米尔语", "te": "泰卢固语", "ur": "乌尔都语", "uk": "乌克兰语",
    "bg": "保加利亚语", "hr": "克罗地亚语", "sr": "塞尔维亚语", "sl": "斯洛文尼亚语",
    "ca": "加泰罗尼亚语", "fa": "波斯语", "sw": "斯瓦希里语", "af": "南非荷兰语",
    "am": "阿姆哈拉语", "az": "阿塞拜疆语", "be": "白俄罗斯语", "bs": "波斯尼亚语",
    "et": "爱沙尼亚语", "eu": "巴斯克语", "fil": "菲律宾语", "ga": "爱尔兰语",
    "gl": "加利西亚语", "gu": "古吉拉特语", "hy": "亚美尼亚语", "is": "冰岛语",
    "ka": "格鲁吉亚语", "kk": "哈萨克语", "km": "高棉语", "kn": "卡纳达语",
    "lo": "老挝语", "lt": "立陶宛语", "lv": "拉脱维亚语", "mk": "马其顿语",
    "ml": "马拉雅拉姆语", "mn": "蒙古语", "mr": "马拉地语", "mt": "马耳他语",
    "my": "缅甸语", "ne": "尼泊尔语", "ps": "普什图语", "pt": "葡萄牙语",
    "so": "索马里语", "sq": "阿尔巴尼亚语", "uz": "乌兹别克语", "zu": "祖鲁语",
    "jv": "爪哇语", "yue": "粤语", "wuu": "吴语", "zh": "中文",
    # 这些有国家变体，靠前缀兜底
    "de": "德语", "fr": "法语", "es": "西班牙语", "it": "意大利语",
    "ja": "日语", "ko": "韩语", "cy": "威尔士语", "gd": "苏格兰盖尔语",
    "lb": "卢森堡语", "mi": "毛利语", "sm": "萨摩亚语", "to": "汤加语",
    "iu": "因纽特语", "si": "僧伽罗语", "su": "巽他语", "ha": "豪萨语",
    "yo": "约鲁巴语", "ig": "伊博语", "ti": "提格里尼亚语", "om": "奥罗莫语",
}

_EN_REGION = {
    "US": "美", "GB": "英", "AU": "澳", "CA": "加", "IN": "印", "IE": "爱",
    "NZ": "新", "NG": "尼日利亚", "ZA": "南非", "KE": "肯尼亚", "TZ": "坦桑尼亚",
    "PH": "菲律宾", "SG": "新加坡", "HK": "香港",
}


def _locale_info(loc: str):
    if loc in _LOCALE_CN:
        cn, group = _LOCALE_CN[loc]
        if group == "其他外语":
            group = cn.split("（")[0]
        return (cn, group)
    parts = loc.split("-")
    lang = parts[0].lower()
    region = parts[-1].upper() if len(parts) > 1 else ""

    # zh-CN-xxx 形式的其他方言
    if lang == "zh" and len(parts) > 2:
        return (parts[2], "中文·方言")
    if lang == "zh":
        return ("中文", "中文·方言")

    if lang == "en":
        cn = f"英语（{_EN_REGION.get(region, region)}）" if region else "英语"
        return (cn, "英语")

    cn = _LANG_CN.get(lang)
    if cn:
        # 每种语言各自成组，避免几百个音色挤在「其他」里
        return (cn, cn)
    return (loc, f"其他（{loc}）")


def _friendly(short_name: str, locale: str, gender: str) -> str:
    key = short_name.split("-")[-1].replace("Neural", "")
    name = _VOICE_NAME.get(key, key)
    loc_cn, _ = _locale_info(locale)
    g = _GENDER_LABEL.get(gender, gender)
    return f"{name} · {loc_cn} · {g}"


# ---------------------------------------------------------------- 语音设置

# 语音服务目录：按优先级挑选第一个真实存在的（换机/迁移后不易错位）
_VOICE_CANDIDATES = [
    os.getenv("VOICE_DIR", ""),
    str(Path(__file__).resolve().parent.parent.parent / "voice-server" / "main" / "xiaozhi-server"),
    r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server",
    r"D:\AI-Companion-shared\xiaohui-ai\voice-server\main\xiaozhi-server",
]
VOICE_DIR = None
for _c in _VOICE_CANDIDATES:
    if _c and (Path(_c) / "data").is_dir():
        VOICE_DIR = Path(_c).resolve()
        break
if VOICE_DIR is None:
    VOICE_DIR = Path(_VOICE_CANDIDATES[1]).resolve()
VOICE_SETTINGS = VOICE_DIR / "data" / "voice_settings.json"

# 三档：慢 / 标准 / 快；音调：低 / 标准 / 高
_RECOGNIZE_MS = [900, 600, 350]
_RATE = ["-10%", "+0%", "+25%"]
_PITCH_HZ = ["-12Hz", "+0Hz", "+12Hz"]
_DEFAULT_VOICE = {"recognize": 2, "speed": 2, "pitch": 1}


class VoiceSettingsIn(BaseModel):
    recognize: int = 2   # 0 慢 / 1 标准 / 2 快
    speed: int = 2       # 0 慢 / 1 标准 / 2 快
    pitch: int = 1       # 0 低 / 1 标准 / 2 高
    voice: str = ""      # Edge TTS 音色 id，空表示不改


def _resolve_voice_settings(s: Dict[str, Any]) -> Dict[str, Any]:
    r = max(0, min(2, int(s.get("recognize", 2))))
    sp = max(0, min(2, int(s.get("speed", 2))))
    p = max(0, min(2, int(s.get("pitch", 1))))
    out = {
        "recognize": r, "speed": sp, "pitch": p,
        "silence_ms": _RECOGNIZE_MS[r],
        "rate": _RATE[sp],
        "pitch_hz": _PITCH_HZ[p],
    }
    if s.get("voice"):
        out["voice"] = str(s["voice"])
    if s.get("model"):
        out["model"] = str(s["model"])
    if s.get("prompt"):
        out["prompt"] = str(s["prompt"])
    if s.get("wakeup_words"):
        out["wakeup_words"] = list(s["wakeup_words"])
    return out


def _read_voice_settings() -> Dict[str, Any]:
    cur: Dict[str, Any] = dict(_DEFAULT_VOICE)
    if VOICE_SETTINGS.exists():
        try:
            data = json.loads(VOICE_SETTINGS.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cur.update(data)
        except Exception:
            pass
    return cur


def _write_voice_settings(cur: Dict[str, Any]) -> Dict[str, Any]:
    out = _resolve_voice_settings(cur)
    VOICE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    VOICE_SETTINGS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _sync_engine_voice(voice_id: str) -> None:
    """把控制台选的音色写进语音服务的运行时配置（失败不影响主流程）。"""
    try:
        cur = _read_voice_settings()
        if cur.get("voice") == voice_id:
            return
        cur["voice"] = voice_id
        _write_voice_settings(cur)
        store.add_log("system", f"设备音色切换为 {voice_id}（下一轮对话生效）")
    except Exception:
        pass


def _sync_engine_prompt(persona: str) -> None:
    """把角色介绍写进语音服务的运行时配置（下一通连接生效）。"""
    try:
        cur = _read_voice_settings()
        if cur.get("prompt") == persona:
            return
        cur["prompt"] = persona
        _write_voice_settings(cur)
        store.add_log("system", "角色设定已同步到语音服务（下一轮对话生效）")
    except Exception:
        pass


def _sync_engine_wakeup(word: str) -> None:
    """把唤醒词并入语音服务的识别列表，不覆盖设备端已支持的词。"""
    try:
        cur = _read_voice_settings()
        words = list(cur.get("wakeup_words") or [])
        if "你好小慧" not in words:
            words.insert(0, "你好小慧")
        if word and word not in words:
            words.append(word)
        if words == (cur.get("wakeup_words") or []):
            return
        cur["wakeup_words"] = words
        _write_voice_settings(cur)
        store.add_log("system", f"唤醒词列表已更新：{', '.join(words)}")
    except Exception:
        pass


def _sync_engine_model(model_name: str) -> None:
    """把控制台选的模型写进语音服务的运行时配置。"""
    try:
        cur = _read_voice_settings()
        if cur.get("model") == model_name:
            return
        cur["model"] = model_name
        _write_voice_settings(cur)
        store.add_log("system", f"设备对话模型切换为 {model_name}（下一轮对话生效）")
    except Exception:
        pass


@app.get("/api/voice/settings")
def api_voice_settings_get():
    cur = _read_voice_settings()
    out = _resolve_voice_settings(cur)
    out["voice"] = cur.get("voice", "")
    out["applied"] = VOICE_SETTINGS.exists()
    return out


@app.post("/api/voice/settings")
def api_voice_settings_set(body: VoiceSettingsIn):
    """写入语音服务目录下的运行时配置，下一次识别/合成立即生效。"""
    cur = _read_voice_settings()
    payload = body.model_dump()
    if not payload.get("voice"):
        payload["voice"] = cur.get("voice", "")
    try:
        out = _write_voice_settings({**cur, **payload})
    except Exception as e:
        raise HTTPException(500, f"写入语音服务配置失败：{e}")
    store.add_log(
        "system",
        f"语音设置已更新：静音判定 {out['silence_ms']}ms / 语速 {out['rate']} / 音调 {out['pitch_hz']}"
        + (f" / 音色 {out['voice']}" if out.get("voice") else ""),
    )
    out["applied"] = True
    return out


@app.get("/api/voices")
def api_voices(refresh: bool = False):
    """真实音色列表（Edge TTS，全部语种），带缓存。"""
    now = time.time()
    if not refresh and _voice_cache["voices"] and now - _voice_cache["at"] < 3600:
        return {"source": "edge-tts", "cached": True,
                "voices": _voice_cache["voices"], **_voice_meta(_voice_cache["voices"])}
    try:
        import asyncio
        import edge_tts

        raw = asyncio.run(edge_tts.list_voices())
        voices = []
        for v in raw:
            short = v.get("ShortName", "")
            loc = v.get("Locale", "")
            loc_cn, group = _locale_info(loc)
            voices.append({
                "id": short,
                "label": _friendly(short, loc, v.get("Gender", "")),
                "locale": loc,
                "locale_cn": loc_cn,
                "group": group,
                "gender": _GENDER_LABEL.get(v.get("Gender", ""), v.get("Gender", "")),
            })
        # 中文排最前，其余按分组名
        order = {"中文": 0, "中文·方言": 1, "英语": 2}
        voices.sort(key=lambda x: (order.get(x["group"], 9), x["group"], x["label"]))
        _voice_cache.update({"at": now, "voices": voices})
        return {"source": "edge-tts", "cached": False, "voices": voices,
                **_voice_meta(voices)}
    except Exception as e:
        fallback = [
            {"id": "zh-CN-XiaoxiaoNeural", "label": "晓晓 · 普通话 · 女声",
             "locale": "zh-CN", "locale_cn": "普通话", "group": "中文", "gender": "女声"},
            {"id": "zh-CN-YunxiNeural", "label": "云希 · 普通话 · 男声",
             "locale": "zh-CN", "locale_cn": "普通话", "group": "中文", "gender": "男声"},
        ]
        return {"source": "builtin", "cached": False, "reason": str(e),
                "voices": fallback, **_voice_meta(fallback)}


def _voice_meta(voices: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups: Dict[str, int] = {}
    for v in voices:
        groups[v["group"]] = groups.get(v["group"], 0) + 1
    return {
        "groups": [{"name": k, "count": n}
                   for k, n in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))],
        "total": len(voices),
    }


# 试听示例文本：按语种给对应语言的句子，避免跨语言合成失败
_SAMPLE_TEXT = {
    "zh": "你好，我是小慧，很高兴认识你。",
    "en": "Hi, I'm Xiaohui. Nice to meet you.",
    "ja": "こんにちは、小慧です。よろしくお願いします。",
    "ko": "안녕하세요, 샤오샤오입니다. 만나서 반갑습니다.",
    "fr": "Bonjour, je suis Xiaohui. Enchanté de vous rencontrer.",
    "de": "Hallo, ich bin Xiaohui. Schön, dich kennenzulernen.",
    "es": "Hola, soy Xiaohui. Encantado de conocerte.",
    "ru": "Привет, я Сяосяо. Рад познакомиться.",
    "it": "Ciao, sono Xiaohui. Piacere di conoscerti.",
    "pt": "Olá, eu sou Xiaohui. Prazer em conhecê-lo.",
    "ar": "مرحبا، أنا شياوشياو. سعيد بلقائك.",
    "th": "สวัสดี ฉันชื่อเสียวเสียว ยินดีที่ได้รู้จัก",
    "vi": "Xin chào, tôi là Xiaohui. Rất vui được gặp bạn.",
}


def _sample_for(voice_id: str) -> str:
    lang = voice_id.split("-")[0].lower()
    return _SAMPLE_TEXT.get(lang, _SAMPLE_TEXT["en"])


@app.get("/api/voices/{voice_id}/sample")
def api_voice_sample(voice_id: str, text: str = ""):
    """现场合成一小段音频，用于试听。文本按语种自动选择。"""
    try:
        candidates = [text] if text.strip() else []
        candidates += [_sample_for(voice_id), _SAMPLE_TEXT["en"], "Hello, nice to meet you."]

        audio = b""
        last_err = ""
        for t in candidates:
            if not t:
                continue
            try:
                audio = _tts_bytes(t, voice_id)
                if audio:
                    break
            except Exception as e:
                last_err = str(e)
                continue

        if not audio:
            raise RuntimeError(last_err or "没有音频数据")
        return StreamingResponse(iter([audio]), media_type="audio/mpeg",
                                 headers={"Cache-Control": "no-store"})
    except Exception as e:
        raise HTTPException(502, f"试听失败：{e}")


@app.get("/api/stats")
def api_stats():
    """仪表盘：一屏看完设备、对话、知识库、模型状态。"""
    s = store.stats()
    st = llm.status()

    kb = {"enabled": False, "docs": 0, "chunks": 0, "embed": "", "vector": ""}
    if KB_URL:
        try:
            with httpx.Client(timeout=5.0) as c:
                h = c.get(f"{KB_URL}/health").json()
                docs = c.get(f"{KB_URL}/kb/docs").json().get("docs", [])
            kb = {
                "enabled": bool(h.get("ok")),
                "docs": len(docs),
                "chunks": sum(d.get("chunks", 0) for d in docs),
                "embed": h.get("embed_backend", ""),
                "vector": h.get("vector_backend", ""),
            }
        except Exception as e:
            kb["reason"] = str(e)

    s["kb"] = kb
    s["model"] = {
        "provider": st.get("provider"),
        "online": st.get("online"),
        "models": st.get("models", []),
        "hint": st.get("hint", ""),
    }
    return s


# ---------------------------------------------------------------- 设备接入（OTA）
# 完全对齐小智固件的协议：设备开机 POST /ota/，服务器决定
#   - 要不要升级固件
#   - 给了激活码（未绑定）还是 WebSocket 地址（已绑定）

def _ver_tuple(v: str):
    out = []
    for part in str(v or "").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def _is_newer(remote: str, local: str) -> bool:
    a, b = _ver_tuple(remote), _ver_tuple(local)
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def _ws_url_for(request: Request) -> str:
    """按设备实际访问到的地址生成 websocket 地址。

    设备从哪个 IP 访问到控制台，就下发哪个 IP 的语音服务地址，
    这样电脑换网络（热点 / 校园网 / 有线）后不需要改配置。
    """
    from urllib.parse import urlparse

    if WS_URL:
        cfg = WS_URL
    else:
        # 未配置 WS_URL：用设备访问控制台时的 Host（最可靠），否则退回局域网 IP
        host = ''
        try:
            host = (request.url.hostname or '')
        except Exception:
            host = ''
        if not host or host in ('127.0.0.1', 'localhost', '0.0.0.0'):
            try:
                host = request.client.host if request.client else ''
            except Exception:
                host = ''
        if not host or host in ('127.0.0.1', 'localhost'):
            import socket as _s

            try:
                _u = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
                _u.connect(("192.168.255.255", 80))
                host = _u.getsockname()[0]
                _u.close()
            except Exception:
                host = '127.0.0.1'
        cfg = f"ws://{host}:8000/xiaozhi/v1/"
    try:
        p = urlparse(cfg)
        port = p.port or 8000
        path = p.path or "/xiaozhi/v1/"
    except Exception:
        port, path = 8000, "/xiaozhi/v1/"

    host = (request.headers.get("host") or "").split(":")[0].strip()
    if not host:
        host = request.client.host if request.client else "127.0.0.1"
    return f"ws://{host}:{port}{path}"


@app.post("/ota/")
@app.get("/ota/")
async def ota(request: Request):
    mac = request.headers.get("Device-Id", "")
    body: Dict[str, Any] = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    mac = mac or body.get("mac_address", "") or "unknown"
    app_ver = ((body.get("application") or {}).get("version") or "") if isinstance(body, dict) else ""
    client_ip = request.client.host if request.client else ""

    dev = store.register_device(mac, app_ver, client_ip)
    cfg = store.device_config(mac) or {}

    resp: Dict[str, Any] = {
        "server_time": {"timestamp": int(time.time()), "timezone_offset": 480},
    }

    # 1) 固件升级
    fw = store.latest_firmware()
    if fw and _is_newer(fw["version"], app_ver):
        base = str(request.base_url).rstrip("/")
        resp["firmware"] = {
            "version": fw["version"],
            "url": f"{base}/firmware/{fw['filename']}",
            "force": 0,
        }
        store.add_log("system", f"通知设备 {mac} 升级到 {fw['version']}")

    # 2) 未绑定 → 下发激活码；已绑定 → 只下发语音服务地址
    #    注意：绑定成功后必须「不带 activation」，否则固件会认为还需要激活，
    #    进入 application.cc 的激活重试循环，永远走不到连接语音服务那一步。
    if not dev["bound"]:
        resp["activation"] = {
            "code": dev["code"],
            "message": f"请在控制台输入激活码 {dev['code']} 绑定「小慧」",
            "timeout_ms": 300000,
        }
    else:
        # 始终下发地址：由 _ws_url_for 依据设备访问时的 Host 生成，
        # 换网络也不需要改配置（之前未设 WS_URL 就漏发，设备重启后连不上）
        resp["websocket"] = {
            "url": _ws_url_for(request),
            "token": WS_TOKEN,
            "version": 1,
        }

    store.add_log("system", f"OTA 请求 mac={mac} ver={app_ver} bound={dev['bound']}")
    return resp


# ---------------------------------------------------------------- 固件管理

@app.get("/api/firmware")
def api_firmwares():
    return {"firmwares": store.list_firmwares(), "ws_url": WS_URL}


@app.post("/api/firmware")
async def api_firmware_upload(file: UploadFile = File(...), version: str = Form(""), notes: str = Form("")):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "空文件")
    ver = version.strip() or time.strftime("%Y.%m.%d")
    name = f"{ver.replace('/', '_')}_{file.filename}"
    (FIRMWARE_DIR / name).write_bytes(raw)
    fw = store.add_firmware(ver, name, len(raw), notes)
    store.add_log("system", f"上传固件 {ver}（{len(raw)} 字节）")
    return fw


@app.get("/firmware/{filename}")
def api_firmware_download(filename: str):
    path = (FIRMWARE_DIR / filename).resolve()
    if not str(path).startswith(str(FIRMWARE_DIR.resolve())) or not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="application/octet-stream", filename=filename)


@app.delete("/api/firmware/{fid}")
def api_firmware_delete(fid: str):
    fw = store.get_firmware(fid)
    if not fw:
        raise HTTPException(404, "not found")
    (FIRMWARE_DIR / fw["filename"]).unlink(missing_ok=True)
    store.delete_firmware(fid)
    return {"deleted": fid}


# ---------------------------------------------------------------- MCP 工具（代理成员 A 的 model-service）

def _mcp_headers() -> Dict[str, str]:
    """写操作令牌只在后端拼装，绝不下发浏览器。"""
    h = {"Content-Type": "application/json"}
    if MCP_ADMIN_TOKEN:
        h["X-MCP-Admin-Token"] = MCP_ADMIN_TOKEN
    return h


def _mcp_get(path: str, timeout: float = 10.0) -> Any:
    if not MCP_BASE:
        raise HTTPException(503, "未配置 MCP_BASE_URL，MCP 功能不可用")
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"{MCP_BASE}{path}", headers=_mcp_headers())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text[:200])
    except Exception as e:
        raise HTTPException(502, f"连不上 MCP 服务（{MCP_BASE}）：{e}")


def _mcp_call(method: str, path: str, body: Optional[Dict[str, Any]] = None,
              timeout: float = 30.0) -> Any:
    if not MCP_BASE:
        raise HTTPException(503, "未配置 MCP_BASE_URL，MCP 功能不可用")
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.request(method, f"{MCP_BASE}{path}",
                          headers=_mcp_headers(), json=body)
            r.raise_for_status()
            return r.json() if r.content else {"ok": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text[:300])
    except Exception as e:
        raise HTTPException(502, f"连不上 MCP 服务（{MCP_BASE}）：{e}")


@app.get("/api/mcp/status")
def api_mcp_status():
    """连通性 + 汇总计数，供页面顶部状态条使用。"""
    if not MCP_BASE:
        return {"online": False, "base": "", "admin_url": "",
                "servers": 0, "tools": 0, "token_configured": bool(MCP_ADMIN_TOKEN),
                "reason": "未配置 MCP_BASE_URL"}
    try:
        with httpx.Client(timeout=6.0) as c:
            servers = c.get(f"{MCP_BASE}/api/mcp/servers", headers=_mcp_headers()).json()
            tools = c.get(f"{MCP_BASE}/api/mcp/tools", headers=_mcp_headers()).json()
        return {
            "online": True,
            "base": MCP_BASE,
            "admin_url": f"{MCP_BASE}/mcp-admin",
            "servers": len(servers.get("servers", servers if isinstance(servers, list) else [])),
            "tools": len(tools.get("tools", [])),
            "token_configured": bool(MCP_ADMIN_TOKEN),
        }
    except Exception as e:
        return {"online": False, "base": MCP_BASE,
                "admin_url": f"{MCP_BASE}/mcp-admin", "reason": str(e)}


@app.get("/api/mcp/servers")
def api_mcp_servers():
    return _mcp_get("/api/mcp/servers")


@app.get("/api/mcp/tools")
def api_mcp_tools():
    return _mcp_get("/api/mcp/tools")


@app.get("/api/mcp/calls")
def api_mcp_calls(limit: int = 50):
    return _mcp_get(f"/api/mcp/calls?limit={limit}")


@app.get("/api/mcp/events")
def api_mcp_events(limit: int = 50):
    return _mcp_get(f"/api/mcp/events?limit={limit}")


@app.post("/api/mcp/servers/{sid}/refresh")
def api_mcp_refresh(sid: str):
    return _mcp_call("POST", f"/api/mcp/servers/{sid}/refresh", timeout=40.0)


class McpPatchIn(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    read_only: Optional[bool] = None


@app.patch("/api/mcp/servers/{sid}")
def api_mcp_patch(sid: str, body: McpPatchIn):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    return _mcp_call("PATCH", f"/api/mcp/servers/{sid}", payload, timeout=20.0)


class McpTestIn(BaseModel):
    arguments: Dict[str, Any] = {}


@app.post("/api/mcp/tools/{name}/test")
def api_mcp_test(name: str, body: McpTestIn):
    return _mcp_call("POST", f"/api/mcp/tools/{name}/test",
                     {"arguments": body.arguments}, timeout=40.0)


# ---------------------------------------------------------------- 音乐服务

@app.get("/api/music/status")
def api_music_status():
    try:
        with httpx.Client(timeout=6.0) as c:
            r = c.get(f"{MUSIC_BASE}/rest/health")
            r.raise_for_status()
            return {"online": True, "base": MUSIC_BASE, **r.json()}
    except Exception as e:
        return {"online": False, "base": MUSIC_BASE, "reason": str(e)}


@app.get("/api/music/search")
def api_music_search(q: str = "", limit: int = 5):
    if not q.strip():
        return {"ok": False, "songs": [], "error": "关键词为空"}
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(f"{MUSIC_BASE}/rest/search", params={"q": q, "limit": limit})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")

@app.get("/api/music/recommend")
def api_music_recommend(mood: str = "放松", limit: int = 5):
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(f"{MUSIC_BASE}/rest/recommend", params={"mood": mood, "limit": limit})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")


# ---------------------------------------------------------------- 本地曲库（整首播放）

AUDIO_EXT = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".aac", ".opus"}


def _scan_library() -> List[Dict[str, Any]]:
    items = []
    for p in sorted(MUSIC_DIR.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in AUDIO_EXT:
            continue
        rel = p.relative_to(MUSIC_DIR).as_posix()
        items.append({
            "id": rel,
            "title": p.stem,
            "folder": str(p.parent.relative_to(MUSIC_DIR)) if p.parent != MUSIC_DIR else "",
            "size_mb": round(p.stat().st_size / 1048576, 1),
            "url": f"/api/music/local/{rel}",
        })
    return items


@app.get("/api/music/local")
def api_music_local():
    items = _scan_library()
    return {"dir": str(MUSIC_DIR), "count": len(items), "tracks": items}


@app.get("/api/music/local/{track_path:path}")
def api_music_local_stream(track_path: str):
    """整首播放：支持 Range，浏览器拖进度条不会卡。"""
    path = (MUSIC_DIR / track_path).resolve()
    if not str(path).startswith(str(MUSIC_DIR)) or not path.is_file():
        raise HTTPException(404, "找不到这个文件")
    if path.suffix.lower() not in AUDIO_EXT:
        raise HTTPException(400, "不是音频文件")
    return FileResponse(path, filename=path.name)


def _normalize_tts_text(text: str) -> str:
    """补标点：Edge TTS 对过短、无标点的文本容易返回空音频。"""
    t = (text or "").strip()
    if not t:
        return ""
    if t[-1] not in "。！？.!?，,、~～":
        t += "。"
    return t


def _tts_bytes(text: str, voice: str, retries: int = 3) -> bytes:
    """合成语音，失败重试；仍失败则换一个音色再试。"""
    import asyncio
    import edge_tts

    text = _normalize_tts_text(text)[:120]
    if not text:
        raise RuntimeError("文本为空")

    voices = [voice] if voice else []
    for fallback in ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"):
        if fallback not in voices:
            voices.append(fallback)

    last_err = ""
    for v in voices:
        for attempt in range(retries):
            try:
                async def synth() -> bytes:
                    comm = edge_tts.Communicate(text, v)
                    buf = bytearray()
                    async for chunk in comm.stream():
                        if chunk.get("type") == "audio":
                            buf.extend(chunk["data"])
                    return bytes(buf)

                audio = asyncio.run(synth())
                if audio:
                    return audio
                last_err = "返回空音频"
            except Exception as e:
                last_err = str(e)
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(last_err or "合成失败")


class AnnounceIn(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"


@app.post("/api/music/announce")
def api_music_announce(body: AnnounceIn):
    """把一句话用 TTS 念出来（例如「找到三首歌」）。"""
    try:
        audio = _tts_bytes(body.text, body.voice)
        return StreamingResponse(iter([audio]), media_type="audio/mpeg",
                                 headers={"Cache-Control": "no-store"})
    except Exception as e:
        raise HTTPException(502, f"语音合成失败：{e}")


# ---------------------------------------------------------------- 知识库代理

@app.get("/api/kb/status")
def api_kb_status():
    if not KB_URL:
        return {"enabled": False, "reason": "未配置 KB_URL"}
    try:
        with httpx.Client(timeout=5.0) as c:
            return {"enabled": True, **c.get(f"{KB_URL}/health").json()}
    except Exception as e:
        return {"enabled": False, "reason": str(e)}


@app.get("/api/kb/docs")
def api_kb_docs():
    if not KB_URL:
        return {"docs": [], "enabled": False}
    try:
        with httpx.Client(timeout=10.0) as c:
            return {"enabled": True, **c.get(f"{KB_URL}/kb/docs").json()}
    except Exception as e:
        return {"docs": [], "enabled": False, "reason": str(e)}


@app.get("/api/kb/docs/{doc_id}/chunks")
def api_kb_doc_chunks(doc_id: str):
    """分段预览：转发到知识库服务。"""
    if not KB_URL:
        raise HTTPException(400, "未配置 KB_URL")
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(f"{KB_URL}/kb/docs/{doc_id}/chunks")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"知识库服务不可用：{e}")


class KbSearchIn(BaseModel):
    query: str
    top_k: int = 5


@app.post("/api/kb/search")
def api_kb_search(body: KbSearchIn):
    """检索测试：返回命中的片段和相关性分数。"""
    if not KB_URL:
        raise HTTPException(400, "未配置 KB_URL")
    if not body.query.strip():
        return {"query": body.query, "hits": []}
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{KB_URL}/kb/search",
                       json={"query": body.query, "top_k": body.top_k})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"知识库服务不可用：{e}")


@app.post("/api/kb/upload")
async def api_kb_upload(file: UploadFile = File(...), title: str = Form("")):
    if not KB_URL:
        raise HTTPException(400, "未配置 KB_URL")
    content = await file.read()
    files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
    data = {"title": title} if title else {}
    try:
        with httpx.Client(timeout=180.0) as c:
            r = c.post(f"{KB_URL}/kb/ingest", files=files, data=data)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)
    except Exception as e:
        raise HTTPException(502, f"知识库服务不可用：{e}")


class TextIn(BaseModel):
    title: str
    text: str


@app.post("/api/kb/ingest_text")
def api_kb_ingest_text(body: TextIn):
    if not KB_URL:
        raise HTTPException(400, "未配置 KB_URL")
    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{KB_URL}/kb/ingest_text", json=body.model_dump())
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"知识库服务不可用：{e}")


@app.delete("/api/kb/docs/{doc_id}")
def api_kb_delete(doc_id: str):
    if not KB_URL:
        raise HTTPException(400, "未配置 KB_URL")
    try:
        with httpx.Client(timeout=30.0) as c:
            c.delete(f"{KB_URL}/kb/docs/{doc_id}")
        return {"deleted": doc_id}
    except Exception as e:
        raise HTTPException(502, f"知识库服务不可用：{e}")


# ---------------------------------------------------------------- 前端

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


# ---------------------------------------------------------------- 在线互动

ACTION_MAP = {
    "stand": "站好了", "sit": "坐下了", "walk": "往前走", "back": "往后退",
    "left": "左转", "right": "右转", "dance": "跳舞中", "lie": "趴下了",
    "sleep": "睡着了", "wake": "起来了", "wag": "摇尾巴", "shake": "摇摇头",
}


class PushIn(BaseModel):
    action: str
    value: str = ""


@app.post("/api/device/push")
async def api_device_push(body: PushIn):
    """把一个动作排进队列，等设备心跳取走执行。"""
    devs = store.list_devices() or []
    # 优先选已绑定、且最近有心跳的设备（避免命中历史幽灵记录）
    devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
    device = devs[0] if devs else None
    if not device:
        return {"ok": False, "error": "没有绑定设备"}
    # 远程唤醒：让设备主动连上语音服务
    if body.action == "connect":
        store.push_command(device["mac"], "connect", "1")
        store.add_log("system", "控制台请求唤醒设备")
        return {"ok": True, "action": "connect", "note": "设备将在 1~2 秒内连接"}

    # 音量指令：action=volume，value=0-100
    if body.action == "volume":
        try:
            _vol = max(0, min(100, int(body.value or 60)))
        except Exception:
            _vol = 60
        store.push_command(device["mac"], "volume", str(_vol))
        store.add_log("system", "控制台设置音量：" + str(_vol))
        return {"ok": True, "volume": _vol}

    if body.action not in ACTION_MAP:
        return {"ok": False, "error": "未知动作"}
    store.push_command(device["mac"], "action", body.action)
    store.add_log("system", "控制台下发动作：" + ACTION_MAP[body.action])
    return {"ok": True, "action": body.action, "tip": ACTION_MAP[body.action]}


@app.get("/chat")
async def chat_page():
    """在线互动页面：打字聊天 + 按钮控制。"""
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "static" / "chat.html"
    if p.exists():
        return Response(content=p.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")
    return Response(content="chat.html 缺失", status_code=500)


# ---------------------------------------------------------------- 语音服务控制

class ConsoleActionIn(BaseModel):
    action: str = ""
    tool: str = ""
    arguments: Dict[str, Any] = {}
    device_id: str = ""


@app.post("/api/console/action")
def api_console_action(body: ConsoleActionIn):
    """代理到语音服务的设备 MCP 控制接口；不可用时退回心跳队列。"""
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE，无法连接语音服务")
    payload = {k: v for k, v in body.model_dump().items() if v not in ("", None, {})}
    if not payload.get("action") and not payload.get("tool"):
        raise HTTPException(400, "缺少 action 或 tool")
    r = None
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/action", json=payload)
    except Exception:
        r = None
    if r is not None and r.status_code < 400:
        try:
            return r.json()
        except Exception:
            return {"ok": True}

    # 语音通道不可用：改用设备心跳队列下发（≤5 秒执行）
    action = payload.get("action")
    if action:
        try:
            devs = store.list_devices() or []
            devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
            if devs:
                store.push_command(devs[0]["mac"], "action", action)
                store.add_log("system", "语音通道不可用，改用心跳下发：" + str(action))
                return {"ok": True, "via": "heartbeat", "action": action,
                        "note": "设备下次心跳（5 秒内）执行"}
        except Exception as exc:
            raise HTTPException(500, f"下发失败：{exc}")
    raise HTTPException(502, "语音服务不可用，且没有可下发的设备")


@app.get("/api/console/status")
def api_console_status():
    """语音服务在线连接与设备 MCP 状态。"""
    if not VOICE_HTTP_BASE:
        return {"ok": False, "online": False, "devices": [],
                "reason": "未配置 VOICE_HTTP_BASE"}
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(f"{VOICE_HTTP_BASE}/api/console/status")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return {"ok": False, "online": False, "devices": [], "reason": str(e)}


# 语音服务不可用时的兜底动作清单（与 core/utils/console_actions.py 保持一致）
_ACTION_FALLBACK = [
    {"action": "stand", "label": "站立", "kind": "preset"},
    {"action": "sit", "label": "坐下", "kind": "preset"},
    {"action": "lie", "label": "趴下", "kind": "preset"},
    {"action": "sleep", "label": "睡觉", "kind": "preset"},
    {"action": "wake", "label": "起身", "kind": "preset"},
    {"action": "walk", "label": "前进", "kind": "preset"},
    {"action": "back", "label": "后退", "kind": "preset"},
    {"action": "left", "label": "左转", "kind": "preset"},
    {"action": "right", "label": "右转", "kind": "preset"},
    {"action": "dance", "label": "跳舞", "kind": "preset"},
    {"action": "wag", "label": "摇尾巴", "kind": "preset"},
    {"action": "shake", "label": "摇头", "kind": "preset"},
    {"action": "handshake", "label": "握手", "kind": "gesture"},
    {"action": "happy", "label": "开心", "kind": "gesture"},
    {"action": "stretch", "label": "伸懒腰", "kind": "gesture"},
    {"action": "spin", "label": "转个圈", "kind": "gesture"},
]


@app.get("/api/console/actions")
def api_console_actions():
    """动作面板目录。

    数据源是语音服务的 GET /api/console/actions（固件预设 + 服务端手势），
    这样「网页按钮 / 语音关键词 / 固件能力」不会各写一份导致漂移。
    语音服务不可用时退回本地清单，页面至少还能点预置动作。
    """
    if VOICE_HTTP_BASE:
        try:
            with httpx.Client(timeout=6.0) as c:
                r = c.get(f"{VOICE_HTTP_BASE}/api/console/actions")
                r.raise_for_status()
                data = r.json()
            actions = data.get("actions") or []
            if actions:
                return {"ok": True, "via": "voice", "actions": actions}
        except Exception as e:
            store.add_log("system", f"动作目录取语音服务失败，用本地清单：{e}")
    return {"ok": True, "via": "fallback", "actions": _ACTION_FALLBACK}


# ---------------------------------------------------------------- 配置导出 / 导入

@app.get("/api/config/export")
def api_config_export():
    """导出当前智能体配置与语音运行时设置。"""
    import json as _json

    agents = store.list_agents()
    agent = store.get_agent(agents[0]["id"]) if agents else None
    voice = _read_voice_settings()
    payload = {
        "version": 1,
        "exported_at": int(time.time()),
        "agent": {
            k: agent.get(k)
            for k in ("name", "persona", "model", "voice", "wake_word",
                      "kb_enabled", "kb_topk", "memory_enabled", "temperature")
        } if agent else None,
        "voice": {
            k: voice.get(k)
            for k in ("recognize", "speed", "pitch", "voice", "model",
                      "prompt", "silence_ms", "wakeup_words")
        },
    }
    from fastapi.responses import Response

    body = _json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="xiaohui-config.json"'
        },
    )


class ConfigImportIn(BaseModel):
    agent: Dict[str, Any] = {}
    voice: Dict[str, Any] = {}


@app.post("/api/config/import")
def api_config_import(body: ConfigImportIn):
    """导入配置，覆盖当前智能体与语音设置。"""
    applied = []
    agents = store.list_agents()
    if body.agent and agents:
        aid = agents[0]["id"]
        cur = store.get_agent(aid)
        merged = dict(cur)
        for k, v in body.agent.items():
            if k in merged and v is not None:
                merged[k] = v
        store.update_agent(aid, merged)
        if merged.get("voice"):
            _sync_engine_voice(merged["voice"])
        if merged.get("model"):
            _sync_engine_model(merged["model"])
        if merged.get("persona"):
            _sync_engine_prompt(merged["persona"])
        if merged.get("wake_word"):
            _sync_engine_wakeup(merged["wake_word"])
        applied.append("智能体")

    if body.voice:
        cur = _read_voice_settings()
        for k, v in body.voice.items():
            if v is not None:
                cur[k] = v
        _write_voice_settings(cur)
        applied.append("语音设置")

    store.add_log("system", "导入配置：" + "、".join(applied or ["无"]))
    return {"ok": True, "applied": applied}


@app.get("/api/memory/list")
async def api_memory_list(limit: int = 100):
    """记忆时间线：按时间倒序返回。"""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{KB_URL}/memory/list", params={"limit": limit})
            return r.json()
    except Exception as e:
        return {"items": [], "error": str(e)}


# ---------------------------------------------------------------- 一键自检

def _probe(url: str, timeout: float = 3.0):
    """返回 (ok, 说明)"""
    import socket
    from urllib.parse import urlparse

    try:
        u = urlparse(url)
        host = u.hostname or "127.0.0.1"
        port = u.port or (443 if u.scheme == "https" else 80)
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True, f"{host}:{port} 可达"
    except Exception as e:
        return False, str(e)[:60]


@app.get("/api/diagnose")
def api_diagnose():
    """把「能不能用」拆成可读的检查项。"""
    import time as _t

    items = []

    # 1) 控制台自身
    items.append({"name": "控制台", "ok": True, "detail": "正在运行", "group": "服务"})

    # 2) 知识库
    ok, d = _probe(KB_URL)
    items.append({"name": "知识库", "ok": ok, "detail": d, "group": "服务"})

    # 3) 音乐 MCP
    ok, d = _probe(os.getenv("MUSIC_BASE_URL", "http://127.0.0.1:8102"))
    items.append({"name": "音乐服务", "ok": ok, "detail": d, "group": "服务"})

    # 4) 语音服务（从 WS_URL 解析端口）
    ws = WS_URL or ""
    ws_host = "127.0.0.1"
    ws_port = 8000
    try:
        from urllib.parse import urlparse

        u = urlparse(ws)
        ws_host = u.hostname or "127.0.0.1"
        ws_port = u.port or 8000
    except Exception:
        pass
    ok_voice, d_voice = _probe(f"http://{ws_host}:{ws_port}")
    items.append({"name": "语音服务", "ok": ok_voice, "detail": d_voice, "group": "服务"})

    # 5) 模型服务
    llm = os.getenv("LLM_CHAT_URL", "")
    if llm:
        from urllib.parse import urlparse

        u = urlparse(llm)
        ok_m, d_m = _probe(f"{u.scheme}://{u.hostname}:{u.port or 80}")
        items.append({"name": "模型服务", "ok": ok_m,
                      "detail": f"{u.hostname}:{u.port} {d_m}", "group": "依赖"})
    else:
        items.append({"name": "模型服务", "ok": False, "detail": "未配置 LLM_CHAT_URL", "group": "依赖"})

    # 6) 设备
    devs = store.list_devices() or []
    bound = [x for x in devs if x.get("bound")]
    if not bound:
        items.append({"name": "设备", "ok": False, "detail": "没有已绑定的设备", "group": "设备"})
    else:
        dev = bound[0]
        age = _t.time() - (dev.get("last_seen") or 0)
        online = age < 120
        items.append({
            "name": "设备",
            "ok": online,
            "detail": ("心跳 %.0f 秒前" % age) + ("，固件 " + (dev.get("firmware") or "-")),
            "group": "设备",
        })

    # 7) 配置生效校验
    agent = None
    agents = store.list_agents()
    if agents:
        agent = store.get_agent(agents[0]["id"])
    vs = _read_voice_settings()
    checks = []
    if agent:
        if vs.get("voice") == agent.get("voice"):
            checks.append({"name": "音色", "ok": True, "saved": agent.get("voice"), "live": vs.get("voice")})
        else:
            checks.append({"name": "音色", "ok": False, "saved": agent.get("voice"), "live": vs.get("voice")})
        if vs.get("model") == agent.get("model"):
            checks.append({"name": "模型", "ok": True, "saved": agent.get("model"), "live": vs.get("model")})
        else:
            checks.append({"name": "模型", "ok": False, "saved": agent.get("model"), "live": vs.get("model")})
        p_live = (vs.get("prompt") or "").strip()
        p_saved = (agent.get("persona") or "").strip()
        checks.append({"name": "角色设定", "ok": bool(p_live) and p_live[:60] == p_saved[:60],
                       "saved": p_saved.splitlines()[0] if p_saved else "(空)",
                       "live": p_live.splitlines()[0] if p_live else "(空)"})
        checks.append({"name": "唤醒词", "ok": bool(vs.get("wakeup_words")),
                       "saved": agent.get("wake_word"),
                       "live": ",".join(vs.get("wakeup_words") or [])})

    return {
        "items": items,
        "config": checks,
        "voice_dir": str(VOICE_DIR),
        "checked_at": int(_t.time()),
    }

@app.post("/api/console/say")
async def api_console_say(request: Request):
    """让在线设备把这段文字说出来（需要设备处于语音会话中）。"""
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "缺少 text")
    try:
        with httpx.Client(timeout=40.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/say", json={"text": text})
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "error": r.text[:200]}
    if r.status_code >= 400:
        return JSONResponse(data, status_code=r.status_code)
    return data


# ---------------------------------------------------------------- 动作编辑

class ActionIn(BaseModel):
    name: str = ""
    angles: str = "90,90,90,90"


@app.get("/api/actions")
def api_actions_list():
    return {"actions": store.list_actions()}


@app.post("/api/actions")
def api_actions_add(body: ActionIn):
    aid = store.add_action(body.name, body.angles)
    store.add_log("system", f"保存动作：{body.name} ({body.angles})")
    return {"ok": True, "id": aid}


@app.delete("/api/actions/{aid}")
def api_actions_delete(aid: int):
    store.delete_action(aid)
    return {"ok": True}


@app.post("/api/device/pose")
def api_device_pose(body: ActionIn):
    """下发一组舵机角度（4 个 + 头部/尾部补 90）。"""
    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
    if not devs:
        raise HTTPException(404, "没有绑定设备")
    parts = [p.strip() for p in body.angles.split(",") if p.strip()]
    while len(parts) < 6:
        parts.append("90")
    value = ",".join(parts[:6])
    store.push_command(devs[0]["mac"], "pose", value)
    store.add_log("system", f"执行姿态：{value}")
    return {"ok": True, "angles": value}


class LedIn(BaseModel):
    value: str = "255,255,255"



@app.post("/api/device/led")
def api_device_led(body: LedIn):
    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
    if not devs:
        raise HTTPException(404, "没有绑定设备")
    store.push_command(devs[0]["mac"], "led", body.value)
    store.add_log("system", f"灯效：{body.value}")
    return {"ok": True}


@app.get("/api/chats/recent")
def api_chats_recent(limit: int = 200):
    return {"chats": store.recent_chats(limit)}


@app.post("/api/memory/clear")
def api_memory_clear():
    n = store.clear_memories()
    store.add_log("system", f"清空记忆 {n} 条")
    return {"ok": True, "removed": n}


@app.post("/api/memory/facts/clear")
async def api_memory_facts_clear():
    """清空长期记忆（知识库 facts），对话轮次保留。"""
    if not KB_URL:
        return {"ok": False, "error": "未配置 KB_URL"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{KB_URL}/memory/facts/clear")
            data = r.json()
        store.add_log("system", f"清空长期记忆 {data.get('removed', 0)} 条")
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/memory/turns/clear")
async def api_memory_turns_clear():
    """清空记忆页的「最近对话」（清的是知识库 turns，不影响长期事实）。"""
    if not KB_URL:
        return {"ok": False, "error": "未配置 KB_URL"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{KB_URL}/memory/turns/clear")
            data = r.json()
        store.add_log("system", f"清空最近对话 {data.get('removed', 0)} 条")
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/chats/clear")
def api_chats_clear():
    n = store.clear_all_chats()
    store.add_log("system", f"清空聊天记录 {n} 条")
    return {"ok": True, "removed": n}

@app.post("/api/music/play_device")
def api_music_play_device(body: Dict[str, Any]):
    """搜索并让设备播放第一首（30 秒试听）。"""
    query = str((body or {}).get("query") or "").strip()
    if not query:
        raise HTTPException(400, "缺少 query")
    base = MUSIC_BASE or "http://127.0.0.1:8102"

    try:
        with httpx.Client(timeout=20.0) as c:
            r = c.get(f"{base}/rest/search", params={"q": query, "limit": 3})
            songs = (r.json() or {}).get("songs") or []
    except Exception as e:
        raise HTTPException(502, f"音乐服务不可用：{e}")
    if not songs:
        return {"ok": False, "error": "没有找到带试听音源的歌曲"}
    song = songs[0]
    url = song.get("preview_url")
    if not url:
        return {"ok": False, "error": "这首没有试听音源"}

    # 走成员 A 的音频转码缓存（24kHz 单声道 MP3，体积小 82%，解决卡顿）
    _cache_base = os.getenv("AUDIO_CACHE_BASE", "http://<你的服务器局域网IP>:8080/audio").rstrip("/")
    if _cache_base:
        import urllib.parse as _up
        # 基地址可能已经带 /audio，避免拼成 /audio/audio
        _sep = "?src=" if _cache_base.endswith("/audio") else "/audio?src="
        url = _cache_base + _sep + _up.quote(url, safe="")
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    # 设备每轮对话结束会断开，放歌前先确保在线
    if not _wait_device_online(12.0):
        return {"ok": False, "error": "设备未在线，请先唤醒设备"}

    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    data["song"] = {"name": song.get("title"), "artist": song.get("artist")}
    store.add_log("system", "设备播放音乐：" + str(song.get("title")))
    return data


@app.get("/api/config/history")
def api_config_history(limit: int = 50):
    return {"history": store.list_config_history(limit)}


class RollbackIn(BaseModel):
    id: int


@app.post("/api/config/rollback")
def api_config_rollback(body: RollbackIn):
    h = store.get_config_history(body.id)
    if not h:
        raise HTTPException(404, "记录不存在")
    agent_id = h.get("agent_id")
    a = store.get_agent(agent_id) if agent_id else None
    if not a:
        raise HTTPException(404, "智能体不存在")
    field = h.get("field")
    old = h.get("old_value")
    if field == "temperature":
        try:
            old = float(old or 0)
        except Exception:
            old = 0.0
    elif field in ("kb_enabled", "memory_enabled"):
        old = str(old).lower() in ("1", "true", "yes")
    elif field == "kb_topk":
        try:
            old = int(old or 3)
        except Exception:
            old = 3
    payload = {k: a.get(k) for k in ("name", "persona", "model", "voice", "wake_word",
                                      "kb_enabled", "kb_topk", "memory_enabled",
                                      "temperature")}
    payload[field] = old
    try:
        inst = AgentIn(**payload)
    except Exception:
        inst = AgentIn()
    api_update_agent(agent_id, inst)
    store.add_config_history(agent_id, field, str(a.get(field)), str(old), source="rollback")
    return {"ok": True, "field": field, "value": old}

@app.post("/api/console/speak")
def api_console_speak(body: Dict[str, Any]):
    """网页播报：先确保设备连上（空闲约 4 秒会断开），连上后立刻推音频。"""
    import time as _t

    text = _strip_model_tag(str((body or {}).get("text") or "").strip())
    if not text:
        raise HTTPException(400, "缺少 text")
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    def _try_say():
        try:
            with httpx.Client(timeout=60.0) as c:
                r = c.post(f"{VOICE_HTTP_BASE}/api/console/say", json={"text": text})
                return r.status_code, r.json()
        except Exception as e:
            return 502, {"ok": False, "error": str(e)}

    code, data = _try_say()
    if code == 200 and data.get("ok"):
        return data

    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: d.get("last_seen") or 0, reverse=True)
    if devs:
        try:
            store.push_command(devs[0]["mac"], "connect", "1")
        except Exception:
            pass

    deadline = _t.time() + 12
    while _t.time() < deadline:
        _t.sleep(0.8)
        code, data = _try_say()
        if code == 200 and data.get("ok"):
            return data

    return {"ok": False, "error": data.get("error") or "设备未响应"}

def _strip_model_tag(text: str) -> str:
    """去掉回复尾部的「—— xiaohui-r3:latest」这类模型标签。"""
    import re as _re

    if not text:
        return text
    out = _re.sub(r"\s*——\s*[^\s]+?:latest\s*$", "", text, flags=_re.I)
    out = _re.sub(r"\s*——\s*[^\s]+?\s*$", "", out)
    return out.strip()

def _wait_device_online(timeout: float = 20.0) -> bool:
    """确保语音服务上有在线设备；没有就下发 connect 并等待（会重复催促）。"""
    import time as _t

    def _count() -> int:
        try:
            with httpx.Client(timeout=8.0) as c:
                return int(c.get(f"{VOICE_HTTP_BASE}/api/console/status").json().get("count") or 0)
        except Exception:
            return 0

    if _count() > 0:
        return True
    devs = store.list_devices() or []
    devs = sorted(devs, key=lambda d: d.get("last_seen") or 0, reverse=True)
    if not devs:
        return False

    deadline = _t.time() + timeout
    nudge = 0
    while _t.time() < deadline:
        if _count() > 0:
            return True
        # 每 1.2 秒重新下发一次 connect（配合 400ms 心跳，连接更快）
        if nudge % 2 == 0:
            try:
                store.push_command(devs[0]["mac"], "connect", "1")
            except Exception:
                pass
        nudge += 1
        _t.sleep(0.8)
    return _count() > 0
    try:
        store.push_command(devs[0]["mac"], "connect", "1")
    except Exception:
        pass
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        _t.sleep(0.8)
        if _count() > 0:
            return True
    return False

@app.post("/api/music/stop")
def api_music_stop():
    """停止设备当前播放。"""
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/stop", json={})
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")

@app.post("/api/music/play_url")
def api_music_play_url(body: Dict[str, Any]):
    """按音频 URL 直接播放（搜索结果点播用）。"""
    url = str((body or {}).get("url") or "").strip()
    title = str((body or {}).get("title") or "")
    artist = str((body or {}).get("artist") or "")
    if not url.startswith("http"):
        raise HTTPException(400, "缺少合法的 url")
    if not VOICE_HTTP_BASE:
        raise HTTPException(503, "未配置 VOICE_HTTP_BASE")

    _cache_base = os.getenv("AUDIO_CACHE_BASE", "http://<你的服务器局域网IP>:8080/audio").rstrip("/")
    if _cache_base:
        import urllib.parse as _up
        # 基地址可能已经带 /audio，避免拼成 /audio/audio
        _sep = "?src=" if _cache_base.endswith("/audio") else "/audio?src="
        url = _cache_base + _sep + _up.quote(url, safe="")

    if not _wait_device_online(12.0):
        return {"ok": False, "error": "设备未在线，请先唤醒设备"}

    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/play", json={"url": url})
            data = r.json()
    except Exception as e:
        raise HTTPException(502, f"语音服务不可用：{e}")
    data["song"] = {"name": title, "artist": artist}
    store.add_log("system", "设备播放音乐：" + (title or url[:40]))
    return data

# ---------------------------------------------------------------- 音频转码转发
# 设备只需要能访问控制台（局域网可达），由控制台转给成员 A 的 8106。
AUDIO_UPSTREAM = os.getenv("AUDIO_UPSTREAM", "http://<本地模型服务器IP>:8106")


@app.get("/audio")
def audio_proxy(src: str = ""):
    """按 iTunes 试听地址取转码后的 MP3（24kHz 单声道）。"""
    if not src.startswith("http"):
        raise HTTPException(400, "缺少合法的 src")
    params = {"src": src}
    try:
        req = httpx.get(
            AUDIO_UPSTREAM.rstrip("/") + "/audio",
            params=params,
            timeout=60.0,
            follow_redirects=True,
        )
    except Exception as e:
        raise HTTPException(502, f"音频转码不可用：{e}")
    if req.status_code != 200:
        raise HTTPException(req.status_code, req.text[:200])
    return Response(
        content=req.content,
        media_type=req.headers.get("content-type", "audio/mpeg"),
        headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"},
    )


@app.get("/audio/health")
def audio_health():
    """转码链路是否健康。"""
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(AUDIO_UPSTREAM.rstrip("/") + "/health")
        return {"ok": r.status_code == 200, "upstream": AUDIO_UPSTREAM,
                "status": r.status_code}
    except Exception as e:
        return {"ok": False, "upstream": AUDIO_UPSTREAM, "error": str(e)}

# ---------------------------------------------------------------- 硬件指令接口（给训练侧）
HARDWARE_TOKEN = ""
HARDWARE_EMOTIONS = {
    "neutral", "happy", "laughing", "sad", "angry", "surprised",
    "sleepy", "thinking", "cool", "love", "confused",
}
HARDWARE_TYPES = {"emotion", "servo_control", "servo_action", "action", "led", "pose"}

_hw_commands: Dict[str, Dict[str, Any]] = {}


def _hw_check_token(request: Request) -> None:
    token = ""
    if token != HARDWARE_TOKEN:
        raise HTTPException(401, "invalid hardware token")


@app.get("/api/hardware/devices")
def api_hw_devices(request: Request):
    """给训练侧看的设备列表（含在线状态）。"""
    _hw_check_token(request)
    now = time.time()
    out = []
    for d in store.list_devices() or []:
        out.append({
            "id": d.get("mac"),
            "name": d.get("name") or "",
            "mac": d.get("mac"),
            "online": bool((d.get("last_seen") or 0) > now - 20),
            "firmware": d.get("firmware") or "",
            "bound": bool(d.get("bound")),
        })
    return {"devices": out}


# ---------------------------------------------------------------- 文字 → 设备指令
LED_COLOR_MAP = {
    "红": (255, 0, 0), "绿": (0, 200, 0), "蓝": (0, 0, 255),
    "黄": (255, 200, 0), "紫": (180, 0, 255), "青": (0, 220, 200),
    "粉": (255, 80, 160), "橙": (255, 120, 0), "白": (255, 255, 255),
}
ACTION_WORDS = {
    "站起来": "stand", "起身": "stand", "站立": "stand", "起来": "stand", "起立": "stand",
    "坐下": "sit", "坐": "sit",
    "趴下": "lie", "趴": "lie",
    "跳舞": "dance", "跳个舞": "dance",
    "前进": "walk", "往前走": "walk", "走两步": "walk",
    "后退": "back", "往后退": "back",
    "左转": "left", "右转": "right",
    "摇尾巴": "wag", "摇摇头": "shake", "摇头": "shake",
    "停下": "stop", "别动": "stop", "停": "stop",
}


CLARIFY_REPLY = "我没太听清，你是想让我做个动作吗？可以说「站起来」「坐下」「红灯」这种。"


def _clarify_reply(text: str) -> str:
    """短指令但没识别到意图时，给一句澄清而不是让模型瞎猜。"""
    t = (text or "").strip()
    if 1 <= len(t) <= 5:
        return CLARIFY_REPLY
    return ""


_DATE_WEEK = "一二三四五六日"


WEATHER_CODE_CN = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "有雾", 48: "有雾", 51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨", 95: "雷阵雨", 96: "雷阵雨伴冰雹",
}


def _extract_city_console(text: str, default: str = "东莞") -> str:
    """从「杭州天气怎么样」里提取城市名。"""
    import re as _re

    noise = ("今天", "明天", "现在", "今晚", "天气", "气温", "温度", "怎么样", "如何",
             "冷不冷", "热不热", "多少度", "几度", "会不会下雨", "下雨吗", "的", "呢",
             "吗", "啊", "呀", "帮我查", "查一下", "看一下")
    s = text or ""
    for w in noise:
        s = s.replace(w, " ")
    for part in sorted(_re.findall(r"[\u4e00-\u9fa5]{2,6}", s), key=len, reverse=True):
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


def _weather_answer(text: str):
    """天气问题直接查 Open-Meteo（固定坐标兜底），返回话术；不相关返回 None。"""
    import httpx as _httpx

    t = (text or "").strip()
    if not t:
        return None
    if not any(k in t for k in ("天气", "气温", "温度", "冷不冷", "热不热", "多少度")):
        return None

    # 城市：从话里提取，支持全国任意城市（地理编码兜底）
    city = _extract_city_console(t, os.getenv("XIAOHUI_DEFAULT_CITY", "东莞"))
    city, lat, lon = _geocode_console(city)

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


_DATE_WEEK = "一二三四五六日"


def _date_answer(text: str):
    """日期/星期问题直接算，避免模型算错。"""
    import datetime as _dt
    import re as _re

    t = (text or "").strip()
    if not t:
        return None

    today = _dt.date.today()
    ask_week = any(k in t for k in ("星期", "周几", "礼拜"))

    if ask_week:
        for kw, delta in (("明天", 1), ("昨天", -1), ("今天", 0), ("今日", 0)):
            if kw in t:
                d = today + _dt.timedelta(days=delta)
                return f"{kw}是 {d.year}年{d.month}月{d.day}日，星期{_DATE_WEEK[d.weekday()]}。"

    m = _re.search(r"(20\d{2})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})", t)
    if m:
        y, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = _dt.date(y, mm, dd)
        except ValueError:
            return None
        return f"{y}年{mm}月{dd}日是星期{_DATE_WEEK[d.weekday()]}。"

    m2 = _re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", t)
    if m2 and ask_week:
        mm, dd = int(m2.group(1)), int(m2.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            try:
                d = _dt.date(today.year, mm, dd)
            except ValueError:
                return None
            return f"{d.year}年{d.month}月{d.day}日是星期{_DATE_WEEK[d.weekday()]}。"

    if any(k in t for k in ("今天几号", "今天日期", "今天多少号", "今天星期几")):
        return f"今天是 {today.year}年{today.month}月{today.day}日，星期{_DATE_WEEK[today.weekday()]}。"

    return None


def _device_cmd_from_text(text: str):
    """从文字里解析设备指令，返回 (kind, value, reply) 或 (None, None, None)。"""
    t = (text or "").strip()
    if not t or len(t) > 40:
        return None, None, None

    # ---------- 灯 ----------
    if any(k in t for k in ("灯", "灯珠", "发光")):
        if any(k in t for k in ("灯光秀", "彩虹", "彩灯", "跑马", "灯效")):
            return "led", "rainbow", "好，来一段彩虹灯光秀。"
        if "呼吸" in t:
            return "led", "breathing", "好，呼吸灯安排。"
        if "闪" in t:
            return "led", "blink", "好，闪给你看。"
        if "流水" in t:
            return "led", "chase", "好，流水灯走起。"
        if any(k in t for k in ("关", "灭", "不要亮", "别亮")):
            return "led", "0,0,0", "好，灯关了。"
        for kw, rgb in LED_COLOR_MAP.items():
            if kw in t:
                return "led", f"{rgb[0]},{rgb[1]},{rgb[2]}", f"好，灯变成{kw}色了。"
        return "led", "255,200,0", "好，灯亮了。"

    # ---------- 动作 ----------
    for word, act in ACTION_WORDS.items():
        if word in t:
            return "action", act, f"好，{word}。"

    return None, None, None


def _push_device_cmd(kind: str, value: str) -> bool:
    """下发到设备心跳队列。"""
    try:
        devs = store.list_devices() or []
        devs = sorted(devs, key=lambda d: (bool(d.get("bound")), d.get("last_seen") or 0), reverse=True)
        if not devs:
            return False
        store.push_command(devs[0]["mac"], kind, value)
        store.add_log("system", f"指令 {kind}={value}")
        return True
    except Exception:
        return False


@app.post("/api/hardware/devices/{device_id}/commands")
def api_hw_command(device_id: str, request: Request, body: Dict[str, Any]):
    """下发一条硬件指令，返回 command.id。"""
    _hw_check_token(request)
    ctype = str((body or {}).get("type") or "").strip()
    params = (body or {}).get("params") or {}

    if ctype not in HARDWARE_TYPES:
        raise HTTPException(400, f"未知指令类型: {ctype}")

    payload_value: Any = None
    if ctype == "emotion":
        emo = str((params or {}).get("emotion") or "").strip().lower()
        if emo not in HARDWARE_EMOTIONS:
            raise HTTPException(400, f"非法 emotion: {emo}")
        payload_value = emo

    cmd_id = uuid.uuid4().hex[:16]
    rec = {
        "id": cmd_id,
        "device_id": device_id,
        "type": ctype,
        "params": params,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": time.time(),
    }
    _hw_commands[cmd_id] = rec

    # 执行：表情走语音服务的设备 MCP（即时），其它先排到心跳队列
    try:
        if ctype == "emotion" and VOICE_HTTP_BASE:
            tool = "self.set_emotion"
            with httpx.Client(timeout=12.0) as c:
                r = c.post(
                    f"{VOICE_HTTP_BASE}/api/console/action",
                    json={"tool": tool, "arguments": {"emotion": payload_value},
                          "device_id": ""},
                )
                data = r.json()
            if data.get("ok"):
                rec["status"] = "executed"
                rec["result"] = "表情已切换"
            else:
                rec["status"] = "failed"
                rec["error"] = data.get("error") or "执行失败"
        else:
            store.push_command(device_id, ctype, str(params.get("value") or ""))
            rec["status"] = "queued"
            rec["result"] = "已排队，等待设备心跳"
    except Exception as e:
        rec["status"] = "failed"
        rec["error"] = str(e)

    store.add_log("system", f"硬件指令 {ctype} → {device_id}: {rec['status']}")
    return {"command": {"id": cmd_id}}


@app.get("/api/hardware/commands/{cmd_id}")
def api_hw_command_status(cmd_id: str, request: Request):
    """查询指令回执。"""
    _hw_check_token(request)
    rec = _hw_commands.get(cmd_id)
    if not rec:
        raise HTTPException(404, "command not found")
    return {"command": rec}

# ---------------------------------------------------------------- 模型预热
WARMUP_INTERVAL = int(os.getenv("LLM_WARMUP_SECONDS", "240"))


def model_warmup():
    """后台线程：定期唤醒模型，避免冷启动 3~5 秒。"""
    import threading

    url = os.getenv("LLM_CHAT_URL", "")
    if not url:
        return

    model = "xiaohui-r5:latest"
    try:
        sf = VOICE_DIR / "data" / "voice_settings.json"
        if sf.exists():
            model = json.loads(sf.read_text(encoding="utf-8")).get("model") or model
    except Exception:
        pass

    def _loop():
        while True:
            try:
                with httpx.Client(timeout=30.0) as c:
                    c.post(url, json={
                        "model": model,
                        "messages": [{"role": "user", "content": "你好"}],
                        "max_tokens": 1,
                        "stream": False,
                    })
            except Exception:
                pass
            threading.Event().wait(WARMUP_INTERVAL)

    th = threading.Thread(target=_loop, name="model-warmup", daemon=True)
    th.start()
    print(f"[warmup] 模型预热已启动：{model}，间隔 {WARMUP_INTERVAL}s", flush=True)


@app.on_event("startup")
def _start_warmup():
    try:
        model_warmup()
    except Exception:
        pass

@app.get("/api/hardware/actions")
def api_hw_actions(request: Request):
    """给语音服务用：返回已保存的自定义动作（name -> angles）。"""
    _hw_check_token(request)
    out = {}
    try:
        for a in store.list_actions() or []:
            out[str(a.get("name"))] = str(a.get("angles") or "")
    except Exception:
        pass
    return {"actions": out}

# ---------------- 在线烧录（USB / esptool）----------------
_FLASH_IMG_DIR = Path(__file__).resolve().parent.parent / "firmware"
_FLASH_IMG_DIR.mkdir(parents=True, exist_ok=True)
_FLASH_STATE = {"running": False, "log": [], "ok": None, "started": None, "image": None}
_ESPTOOL_PY = r"C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe"


@app.get("/api/firmware/ports")
def api_flash_ports(request: Request):
    out = []
    try:
        import serial.tools.list_ports as lp
        for p in lp.comports():
            out.append({"port": p.device, "desc": p.description})
    except Exception:
        pass
    return {"ports": out, "esptool": Path(_ESPTOOL_PY).exists()}


@app.get("/api/firmware/images")
def api_flash_images(request: Request):
    items = []
    for f in sorted(_FLASH_IMG_DIR.glob("*.bin"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024),
            "mtime": time.strftime("%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
        })
    return {"images": items}


@app.post("/api/firmware/flash")
def api_flash_start(request: Request, payload: dict = Body(...)):
    if _FLASH_STATE["running"]:
        return {"ok": False, "error": "已有烧录任务在进行"}
    port = str(payload.get("port") or "").strip()
    image = str(payload.get("image") or "").strip()
    if not port or not image:
        return {"ok": False, "error": "需要选择串口和固件"}

    img_path = _FLASH_IMG_DIR / image
    if not img_path.exists():
        return {"ok": False, "error": "固件文件不存在"}
    if not Path(_ESPTOOL_PY).exists():
        return {"ok": False, "error": "找不到 esptool 环境"}

    _FLASH_STATE.update({"running": True, "log": [], "ok": None,
                         "started": time.strftime("%H:%M:%S"), "image": image})

    def _run():
        cmd = [_ESPTOOL_PY, "-m", "esptool", "--chip", "esp32s3",
               "-p", port, "-b", "460800", "write_flash", "0x0", str(img_path)]
        _FLASH_STATE["log"].append("$ " + " ".join(cmd))
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="ignore")
            for line in p.stdout:
                _FLASH_STATE["log"].append(line.rstrip())
                if len(_FLASH_STATE["log"]) > 300:
                    del _FLASH_STATE["log"][:100]
            p.wait()
            _FLASH_STATE["ok"] = (p.returncode == 0)
        except Exception as e:
            _FLASH_STATE["log"].append(f"异常: {e}")
            _FLASH_STATE["ok"] = False
        finally:
            _FLASH_STATE["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True}


@app.get("/api/firmware/flash/status")
def api_flash_status(request: Request):
    return dict(_FLASH_STATE)

@app.get("/api/health")
def api_health(request: Request):
    """汇总健康检查：各服务是否在线 + 关键参数。"""
    import httpx as _hx

    targets = {
        "语音接口": "http://127.0.0.1:8003/health",
        "语音服务": "tcp://127.0.0.1:8000",
        "大模型专区": "http://127.0.0.1:8013/health",
        "知识库": "http://127.0.0.1:8077/health",
        "音乐服务": "http://127.0.0.1:8102/health",
    }
    out = {"console": "ok", "services": {}}
    for name, url in targets.items():
        try:
            if url.startswith("tcp://"):
                host_port = url[6:].split(":")
                out["services"][name] = "ok" if _port_open(host_port[0], int(host_port[1])) else "down"
            else:
                r = _hx.get(url, timeout=3)
                out["services"][name] = "ok" if r.status_code < 500 else f"http {r.status_code}"
        except Exception:
            out["services"][name] = "down"

    try:
        out["device_online"] = len(_ws_clients())
    except Exception:
        out["device_online"] = None
    out["ok"] = all(v == "ok" for v in out["services"].values())
    return out


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    import socket as _s

    try:
        with _s.create_connection((host, port), timeout) as s:
            s.close()
        return True
    except Exception:
        return False


@app.get("/api/health/music")
def api_health_music(request: Request):
    """音乐服务健康：直接探测 8102 端口。"""
    return {"ok": _port_open("127.0.0.1", 8102), "base": MUSIC_BASE}


@app.get("/api/music/health")
def api_music_health(request: Request):
    """兼容旧路径，内部转给端口探测。"""
    return {"ok": _port_open("127.0.0.1", 8102), "base": MUSIC_BASE}

# ---------------- 动作序列（自定义连续动作） ----------------
_SEQ_FILE = Path(__file__).resolve().parent.parent / "data" / "action_sequences.json"


def _seq_load() -> Dict[str, Any]:
    try:
        if _SEQ_FILE.exists():
            return json.loads(_SEQ_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _seq_save(data: Dict[str, Any]) -> None:
    _SEQ_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SEQ_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


@app.get("/api/actions/sequences")
def api_seq_list(request: Request):
    return {"sequences": _seq_load()}


@app.post("/api/actions/sequences")
def api_seq_save(request: Request, body: dict = Body(...)):
    name = str(body.get("name") or "").strip()
    steps = body.get("steps") or []
    loops = int(body.get("loops") or 1)
    if not name:
        raise HTTPException(400, "动作名不能为空")
    if not steps:
        raise HTTPException(400, "至少要有一个步骤")
    clean = []
    for s in steps[:40]:
        angles = str(s.get("angles") or "").strip()
        ms = int(s.get("ms") or 250)
        if not angles:
            continue
        clean.append({"angles": angles, "ms": max(50, min(ms, 3000))})
    if not clean:
        raise HTTPException(400, "步骤内容为空")
    data = _seq_load()
    data[name] = {"steps": clean, "loops": max(1, min(loops, 20))}
    _seq_save(data)
    return {"ok": True, "count": len(data)}


@app.delete("/api/actions/sequences/{name}")
def api_seq_delete(name: str, request: Request):
    data = _seq_load()
    data.pop(name, None)
    _seq_save(data)
    return {"ok": True}


@app.post("/api/actions/sequences/play")
def api_seq_play(request: Request, body: dict = Body(...)):
    """播放：把步骤交给语音服务，由它通过 MCP 逐帧下发。"""
    name = str(body.get("name") or "").strip()
    data = _seq_load()
    seq = data.get(name)
    if not seq:
        raise HTTPException(404, "动作不存在")
    try:
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{VOICE_HTTP_BASE}/api/console/sequence",
                       json={"steps": seq["steps"], "loops": seq.get("loops", 1)})
            if r.status_code != 200:
                return {"ok": False, "error": f"语音服务返回 {r.status_code}: {r.text[:120]}"}
    except Exception as e:
        return {"ok": False, "error": f"语音服务不可用: {e}"}
    return {"ok": True}
