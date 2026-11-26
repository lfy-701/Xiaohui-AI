"""控制台：动作序列（自定义连续动作）后端。

- 存储：console/data/action_sequences.json
- 接口：
    GET  /api/actions/sequences            列出
    POST /api/actions/sequences            保存 {name, steps:[{angles,ms}], loops}
    DEL  /api/actions/sequences/{name}     删除
    POST /api/actions/sequences/play       播放 {name}（转给语音服务执行）
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

if "/api/actions/sequences" in t:
    print("已存在动作序列接口")
    raise SystemExit(0)

CODE = '''

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
'''

t = t.rstrip() + CODE
P.write_text(t, encoding="utf-8")
ast.parse(t)
print("控制台：动作序列接口已加入")
