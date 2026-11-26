"""控制台：实现成员 A 需要的硬件指令接口（emotion 等）。

- GET  /api/hardware/devices                          设备列表
- POST /api/hardware/devices/{id}/commands            下发指令
- GET  /api/hardware/commands/{cmd_id}                查询回执

鉴权：X-Hardware-Token（环境变量 HARDWARE_TOKEN，默认 <REDACTED>）
执行：emotion 走语音服务 MCP 的 self.set_emotion（即时），失败则如实返回错误
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = F.read_text(encoding="utf-8")

if "/api/hardware/devices" in t:
    print("已存在")
    sys.exit(0)

code = '''

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
'''

t = t.rstrip() + code
F.write_text(t, encoding="utf-8")

# 中间件放行（用 token 鉴权，不走登录态）
lines = F.read_text(encoding="utf-8").split("\n")
idx = None
for i, ln in enumerate(lines):
    if 'if path.startswith("/firmware/"):' in ln:
        idx = i
        break
if idx is not None and 'path.startswith("/api/hardware/")' not in "\n".join(lines):
    indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))
    lines[idx:idx] = [
        indent + "# 训练侧硬件接口：用 X-Hardware-Token 鉴权，不走登录态",
        indent + 'if path.startswith("/api/hardware/"):',
        indent + "    return await call_next(request)",
    ]
    F.write_text("\n".join(lines), encoding="utf-8")

txt = F.read_text(encoding="utf-8")
if "import uuid" not in txt:
    txt = txt.replace("import time", "import time\nimport uuid", 1)
    F.write_text(txt, encoding="utf-8")

ast.parse(F.read_text(encoding="utf-8"))
print("已实现硬件指令接口（emotion 即时执行）；语法 OK")
