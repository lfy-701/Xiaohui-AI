"""语音服务守护 + 日志轮转。

- 每 30 秒检查 8000，挂了自动拉起（带完整环境变量）
- server.log 超过 20 MB 自动切分，保留最近 5 个
"""
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

VOICE = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server")
PY = VOICE / ".venv" / "Scripts" / "python.exe"
LOG = VOICE / "tmp" / "server.log"
PORT = 8000
MAX_MB = 20
KEEP = 5


def up() -> bool:
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", PORT))
        return True
    except Exception:
        return False
    finally:
        s.close()


def rotate_log() -> None:
    try:
        if not LOG.exists() or LOG.stat().st_size < MAX_MB * 1024 * 1024:
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = LOG.with_name(f"server-{stamp}.log")
        shutil.move(str(LOG), str(target))
        LOG.touch()
        olds = sorted(LOG.parent.glob("server-2*.log"))
        for old in olds[:-KEEP]:
            old.unlink(missing_ok=True)
        print(f"[voice-watchdog] 日志已轮转 -> {target.name}", flush=True)
    except Exception as e:
        print(f"[voice-watchdog] 轮转失败: {e}", flush=True)


def env_for_voice() -> dict:
    env = os.environ.copy()
    env.update(
        {
            "USERPROFILE": str(VOICE / ".home"),
            "HOME": str(VOICE / ".home"),
            "MODELSCOPE_CACHE": str(VOICE / ".mscache"),
            "HF_HOME": str(VOICE / ".hfhome"),
            "PATH": str(VOICE / ".venv" / "Scripts") + ";" + env.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "HARDWARE_TOKEN": "<REDACTED>",
            "CONSOLE_URL": "http://127.0.0.1:8080",
            "ZONE_MODE": "all",
            "ZONE_URL": "http://127.0.0.1:8013",
            "ZONE_TIMEOUT": "25",
        }
    )
    return env


def main() -> None:
    print("[voice-watchdog] 启动，间隔 30 秒", flush=True)
    while True:
        rotate_log()
        if not up():
            print("[voice-watchdog] 8000 未响应，正在拉起…", flush=True)
            try:
                # 不要打开 server.log：loguru 轮转时需要独占重命名该文件
                subprocess.Popen(
                    [str(PY), "app.py"],
                    cwd=str(VOICE),
                    env=env_for_voice(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as e:
                print(f"[voice-watchdog] 拉起失败: {e}", flush=True)
            time.sleep(20)
            print(f"[voice-watchdog] 状态: {'已恢复' if up() else '仍在启动中'}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
