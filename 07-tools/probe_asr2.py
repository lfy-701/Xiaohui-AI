"""对比探测：ASRProvider 的参数组合是否触发崩溃。"""
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
    ("A. 加 vad_kwargs", f"""from funasr import AutoModel
m = AutoModel(model=r'{MODEL}', vad_kwargs={{"max_single_segment_time": 30000}}, disable_update=True, device='cpu')
print('A_OK')"""),
    ("B. 加 hub=hf", f"""from funasr import AutoModel
m = AutoModel(model=r'{MODEL}', vad_kwargs={{"max_single_segment_time": 30000}}, disable_update=True, hub='hf', device='cpu')
print('B_OK')"""),
    ("C. 直接构造 ASRProvider", """import sys
sys.path.insert(0, r'C:\\Users\\53487\\Documents\\deepseek-harness\\default-workspace\\voice-server\\main\\xiaozhi-server')
from core.providers.asr.fun_local import ASRProvider
p = ASRProvider({'model_dir': r'""" + MODEL + """', 'output_dir': r'""" + os.path.join(WS, 'tmp', 'asrout') + """'}, True)
print('C_OK')"""),
]

for name, code in PROBES:
    print(f"\n=== {name} ===", flush=True)
    try:
        p = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                           env=env, cwd=WS, timeout=240)
        print(f"  exit={p.returncode}")
        for line in (p.stdout or "").strip().splitlines()[-2:]:
            print("  out:", line[:150])
        for line in (p.stderr or "").strip().splitlines()[-2:]:
            print("  err:", line[:150])
    except subprocess.TimeoutExpired:
        print("  超时（>240s）")
