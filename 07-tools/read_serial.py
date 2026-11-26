"""读 COM4 串口 6 秒，看设备日志（是否在运行、WiFi/WS 状态）。"""
import sys
import time

import serial
import serial.tools.list_ports

sys.stdout.reconfigure(encoding="utf-8")

ports = [p.device for p in serial.tools.list_ports.comports()]
print("串口:", ports)

target = "COM4" if "COM4" in ports else (ports[0] if ports else None)
if not target:
    print("没有可用串口")
    raise SystemExit(1)

try:
    s = serial.Serial(target, 115200, timeout=1)
    s.setDTR(False)
    s.setRTS(False)
    time.sleep(0.3)
    buf = b""
    t0 = time.time()
    while time.time() - t0 < 6:
        buf += s.read(8192)
    s.close()
    txt = buf.decode("utf-8", "ignore")
    print(f"{target} 收到 {len(buf)} 字节")
    for line in txt.splitlines()[-20:]:
        print("  " + line[:130])
except Exception as e:
    print(f"{target} 打开失败: {type(e).__name__} {e}")
