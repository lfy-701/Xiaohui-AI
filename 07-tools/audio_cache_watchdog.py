"""8106 音频转码转发守护：每 30 秒检查端口，挂了自动拉起。"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

RELAY = Path(__file__).with_name("audio_cache_relay.py")
PY = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\.venv\Scripts\python.exe")
PORT = 8106


def port_open() -> bool:
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
    print(f"[watchdog] 开始守护 8106，间隔 30 秒", flush=True)
    while True:
        if not port_open():
            print("[watchdog] 8106 未响应，正在拉起…", flush=True)
            try:
                subprocess.Popen(
                    [str(PY), str(RELAY)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as e:
                print(f"[watchdog] 拉起失败: {e}", flush=True)
            time.sleep(6)
            print(f"[watchdog] 状态: {'已恢复' if port_open() else '仍不可用'}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
