"""大模型专区守护：每 30 秒检查 8013，挂了自动拉起。"""
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ZONE = Path(r"D:\xiaohui-large-zone")
PY = ZONE / ".venv" / "Scripts" / "python.exe"
PORT = 8013


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


def main() -> None:
    print("[zone-watchdog] 启动，间隔 30 秒", flush=True)
    while True:
        if not up():
            print("[zone-watchdog] 8013 未响应，正在拉起…", flush=True)
            try:
                subprocess.Popen(
                    [str(PY), "run_zone.py"],
                    cwd=str(ZONE),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as e:
                print(f"[zone-watchdog] 拉起失败: {e}", flush=True)
            time.sleep(8)
            print(f"[zone-watchdog] 状态: {'已恢复' if up() else '仍不可用'}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
