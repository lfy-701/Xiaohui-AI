"""模型预热：每 4 分钟发一个极小的请求，让模型常驻显存/内存，避免冷启动。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
t = F.read_text(encoding="utf-8")

if "model_warmup" in t:
    print("已存在")
    sys.exit(0)

code = '''

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
'''

t = t.rstrip() + code
F.write_text(t, encoding="utf-8")
ast.parse(t)
print("已加模型预热；语法 OK")
