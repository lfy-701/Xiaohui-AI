import sys, time
import serial

PORT = "COM4"
BAUD = 115200
DUR = int(sys.argv[1]) if len(sys.argv) > 1 else 20

s = serial.Serial(PORT, BAUD, timeout=0.2)
time.sleep(0.3)
# hard reset via RTS/DTR (ESP32 auto-reset)
s.dtr = False
s.rts = True
time.sleep(0.15)
s.rts = False
time.sleep(0.05)

buf = b""
t0 = time.time()
while time.time() - t0 < DUR:
    chunk = s.read(4096)
    if chunk:
        buf += chunk
s.close()

text = buf.decode("utf-8", errors="replace")
for line in text.splitlines():
    line = line.rstrip()
    if line:
        print(line)
