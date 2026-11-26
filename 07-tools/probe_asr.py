"""最小复现：定位 FunASR/PyTorch 崩溃点。分三级逐步加载。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

PY = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\.venv\Scripts\python.exe"
MODEL = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\models\SenseVoiceSmall"
WS = r"C:\Users\53487\Documents\deepseek-harness\default-workspace"

env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["MODELSCOPE_CACHE"] = os.path.join(WS, ".mscache-probe")
env["HF_HOME"] = os.path.join(WS, ".hfhome-probe")
env["USERPROFILE"] = os.path.join(WS, ".home-probe")
env["HOME"] = os.path.join(WS, ".home-probe")
env["PATH"] = os.path.dirname(PY) + ";" + env.get("PATH", "")

PROBES = [
    ("1. torch 基本运算", "import torch; a=torch.randn(64,64); print((a@a).sum().item())"),
    ("2. funasr 导入", "import funasr; print(funasr.__version__)"),
    ("3. AutoModel 加载", f"from funasr import AutoModel; m=AutoModel(model=r'{MODEL}', device='cpu', disable_update=True); print('LOADED')"),
]

for name, code in PROBES:
    print(f"\n=== {name} ===", flush=True)
    p = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                       env=env, cwd=WS, timeout=300)
    out = (p.stdout or "").strip().splitlines()
    err = (p.stderr or "").strip().splitlines()
    print(f"  exit={p.returncode}")
    for line in out[-3:]:
        print("  out:", line[:160])
    for line in err[-3:]:
        print("  err:", line[:160])
