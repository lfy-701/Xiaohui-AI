"""新增 /api/diagnose：一键自检 + 配置生效校验。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = M.read_text(encoding="utf-8")

if "/api/diagnose" in t:
    print("已存在")
    sys.exit(0)

code = '''


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
'''

t = t.rstrip() + code
M.write_text(t, encoding="utf-8")

import ast
ast.parse(t)
print("已加 /api/diagnose，语法 OK")
