"""把语音守护改成不占用 server.log（loguru 需要自己轮转该文件）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

P = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\tools\voice_watchdog.py")
t = P.read_text(encoding="utf-8")

OLD = '''                log = open(LOG, "a", encoding="utf-8", errors="ignore")
                subprocess.Popen(
                    [str(PY), "app.py"],
                    cwd=str(VOICE),
                    env=env_for_voice(),
                    stdout=log,
                    stderr=log,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )'''

NEW = '''                # 不要打开 server.log：loguru 轮转时需要独占重命名该文件
                subprocess.Popen(
                    [str(PY), "app.py"],
                    cwd=str(VOICE),
                    env=env_for_voice(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )'''

if OLD in t:
    P.write_text(t.replace(OLD, NEW, 1), encoding="utf-8")
    print("守护已改为不占用日志")
else:
    print("未匹配，当前内容片段：")
    i = t.find("log = open")
    print(t[max(0, i - 200): i + 300])
