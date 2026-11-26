"""撤回电池电压上报（固件 + 控制台）。"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FW = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai")

# 1) config.h 去掉电池宏
cfg = FW / "config.h"
c = cfg.read_text(encoding="utf-8")
c = re.sub(r"\n// ---------------- 电池检测 ----------------.*?#define BATTERY_EMPTY_MV  3300\n", "\n", c, flags=re.S)
cfg.write_text(c, encoding="utf-8")
print("config.h: 已移除电池宏" if "BATTERY_ADC_PIN" not in c else "⚠ config.h 未清干净")

# 2) dog_board.cc 去掉读取函数与心跳字段
src = FW / "dog_board.cc"
t = src.read_text(encoding="utf-8")

t = re.sub(r"// ---------------- 电池电压 ----------------.*?\n}\n\n", "", t, flags=re.S, count=1)

old_body = re.search(r"        int _mv = ReadBatteryMv\(\);.*?\+ _bat \+ \"\";", t, flags=re.S)
if old_body:
    t = t.replace(old_body.group(0),
                  '''        std::string body = "{\\"mac\\":\\"" + SystemInfo::GetMacAddress() +
                           "\\",\\"firmware\\":\\"" CONSOLE_FIRMWARE_VER "\\"}";''')
    print("dog_board.cc: 心跳已还原")

t = t.replace('#include <esp_adc/adc_oneshot.h>\n#include <esp_adc/adc_cali.h>\n', "")
src.write_text(t, encoding="utf-8")
print("dog_board.cc: 已清理" if "ReadBatteryMv" not in t else "⚠ 仍有残留")

# 3) CMakeLists 去掉 esp_adc
cm = Path(r"D:\xiaozhi-esp32-2.5.2\main\CMakeLists.txt")
m = cm.read_text(encoding="utf-8")
m = m.replace("    list(APPEND MAIN_PRIV_REQUIRES_EXTRA esp_adc)\r\n", "")
m = m.replace("    list(APPEND MAIN_PRIV_REQUIRES_EXTRA esp_adc)\n", "")
cm.write_text(m, encoding="utf-8")
print("CMakeLists: 已移除 esp_adc" if "esp_adc" not in m else "⚠ 仍有 esp_adc")

# 4) 控制台：去掉心跳解析与模型字段
M = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\app\main.py")
mt = M.read_text(encoding="utf-8")
mt = mt.replace('    battery_mv: int = 0\n    battery_pct: int = 0\n', "")
mt = re.sub(r"    # 记录电池电压（固件上报 battery_mv / battery_pct）\n    try:\n.*?\n        pass\n", "", mt, flags=re.S, count=1)
M.write_text(mt, encoding="utf-8")
ast.parse(mt)
print("控制台: 电池解析已移除")
