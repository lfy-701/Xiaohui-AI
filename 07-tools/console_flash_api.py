"""控制台在线烧录：后端接口（列串口 / 列固件 / 开始烧录 / 查询进度）。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = P.read_text(encoding="utf-8")

if "/api/firmware/flash" in t:
    print("已存在烧录接口")
    sys.exit(0)

CODE = '''

# ---------------- 在线烧录（USB / esptool）----------------
_FLASH_IMG_DIR = Path(__file__).resolve().parent.parent / "firmware"
_FLASH_IMG_DIR.mkdir(parents=True, exist_ok=True)
_FLASH_STATE = {"running": False, "log": [], "ok": None, "started": None, "image": None}
_ESPTOOL_PY = r"C:\\Espressif\\tools\\python\\v6.1\\venv\\Scripts\\python.exe"


@app.get("/api/firmware/ports")
def api_flash_ports(request: Request):
    require_login(request)
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
    require_login(request)
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
    require_login(request)
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
    require_login(request)
    return dict(_FLASH_STATE)
'''

# 确保 import
needed = ["import subprocess", "import threading", "import time"]
head = t[:t.find("\n\n")]
for imp in needed:
    if imp not in t:
        t = t.replace("import uuid", f"import uuid\n{imp}", 1)

t = t.rstrip() + CODE
P.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加入在线烧录接口；语法 OK")
