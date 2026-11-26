"""语音执行设备指令时不再说话；动作优先用控制台保存的自定义姿态。

1) 控制台加 /api/hardware/actions（令牌鉴权），返回已保存动作
2) 语音服务：执行后不播报；动作先查自定义姿态，命中发 pose，否则发 action
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------------- 1) 控制台加动作列表接口 ----------------
CON = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
c = CON.read_text(encoding="utf-8")

if "/api/hardware/actions" not in c:
    code = '''

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
'''
    CON.write_text(c.rstrip() + code, encoding="utf-8")
    ast.parse(CON.read_text(encoding="utf-8"))
    print("控制台：已加 /api/hardware/actions")

# ---------------- 2) 语音服务：不播报 + 用自定义姿态 ----------------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\handle\receiveAudioHandle.py")
v = V.read_text(encoding="utf-8")

# 2.1 动作词表改成映射到 key（与控制台动作名一致）
if 'actions = {' in v and '_hw_actions' not in v:
    old = '''    if kind is None:
        actions = {
            "坐下": ("sit", "好，坐下。"), "坐": ("sit", "好，坐下。"),
            "趴下": ("lie", "好，趴下。"), "趴": ("lie", "好，趴下。"),
            "跳舞": ("dance", "好，跳舞给你看。"),
            "站起来": ("stand", "好，站起来。"), "起身": ("stand", "好，起身。"),
            "前进": ("walk", "好，往前走。"), "往前走": ("walk", "好，往前走。"),
            "后退": ("back", "好，往后退。"),
            "左转": ("left", "好，左转。"), "右转": ("right", "好，右转。"),
            "摇尾巴": ("wag", "好，摇尾巴。"),
            "摇摇头": ("shake", "好，摇摇头。"),
            "停下": ("stop", "好，停下。"),
        }
        for word, (act, line) in actions.items():
            if word in t:
                kind, value, say = "action", act, line
                break'''
    new = '''    if kind is None:
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
        }
        for word, act in actions.items():
            if word in t:
                kind, value, say = "action", act, ""
                break'''
    if old in v:
        v = v.replace(old, new, 1)
        print("语音：动作映射已改为 key")
    else:
        print("⚠ 动作词表未匹配")

# 2.2 执行后不说话；动作优先自定义姿态
old_exec = '''    try:
        with _httpx.Client(timeout=10.0) as c:
            devs = c.get(base + "/api/hardware/devices",
                         headers={"X-Hardware-Token": token}).json().get("devices") or []
            if not devs:
                await _speak_ack(conn, "设备还没连上，等一下再试。")
                return True
            did = devs[0]["id"]
            c.post(f"{base}/api/hardware/devices/{did}/commands",
                   headers={"X-Hardware-Token": token},
                   json={"type": kind, "params": {"value": value}})
        await _speak_ack(conn, say)
        return True
    except Exception:
        return False'''

new_exec = '''    try:
        with _httpx.Client(timeout=10.0) as c:
            devs = c.get(base + "/api/hardware/devices",
                         headers={"X-Hardware-Token": token}).json().get("devices") or []
            if not devs:
                return True          # 设备不在线：静默结束，不播报
            did = devs[0]["id"]

            # 动作优先用控制台保存的自定义姿态
            if kind == "action":
                try:
                    saved = c.get(base + "/api/hardware/actions",
                                  headers={"X-Hardware-Token": token}).json().get("actions") or {}
                    angles = saved.get(value)
                    if angles:
                        c.post(f"{base}/api/hardware/devices/{did}/commands",
                               headers={"X-Hardware-Token": token},
                               json={"type": "pose", "params": {"value": angles}})
                        return True
                except Exception:
                    pass

            c.post(f"{base}/api/hardware/devices/{did}/commands",
                   headers={"X-Hardware-Token": token},
                   json={"type": kind, "params": {"value": value}})
        return True
    except Exception:
        return False'''

if old_exec in v:
    v = v.replace(old_exec, new_exec, 1)
    print("语音：执行后静默 + 支持自定义姿态")
else:
    print("⚠ 执行块未匹配")

V.write_text(v, encoding="utf-8")
ast.parse(v)
print("语法 OK")
