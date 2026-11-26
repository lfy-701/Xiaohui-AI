"""电池电压上报：固件读 ADC 随心跳上报，控制台存储并展示。

注意：GPIO1 是占位，需要按实际 PCB 分压网络改 BATTERY_ADC_PIN。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FW = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai")

# ---------- 1) config.h 加电池配置 ----------
cfg = FW / "config.h"
c = cfg.read_text(encoding="utf-8")
if "BATTERY_ADC_PIN" not in c:
    c = c.replace("#define SERVO_COUNT           6", """#define SERVO_COUNT           6

// ---------------- 电池检测 ----------------
// 需要按实际 PCB 分压网络修改：ADC 引脚、分压比（R1+R2)/R2
#define BATTERY_ADC_PIN   GPIO_NUM_1
#define BATTERY_DIVIDER   2.0f
#define BATTERY_FULL_MV   4200
#define BATTERY_EMPTY_MV  3300""")
    cfg.write_text(c, encoding="utf-8")
    print("config.h: 已加电池配置")

# ---------- 2) dog_board.cc 读电压并上报 ----------
src = FW / "dog_board.cc"
t = src.read_text(encoding="utf-8")

if "ReadBatteryMv" not in t:
    helper = '''
// ---------------- 电池电压 ----------------
static int ReadBatteryMv() {
#ifdef BATTERY_ADC_PIN
    static bool inited = false;
    if (!inited) {
        adc_oneshot_unit_handle_t h = nullptr;
        adc_oneshot_unit_init_cfg_t init_cfg = {};
        init_cfg.unit_id = ADC_UNIT_1;
        if (adc_oneshot_new_unit(&init_cfg, &h) != ESP_OK) {
            return -1;
        }
        adc_oneshot_chan_cfg_t ch = {};
        ch.bitwidth = ADC_BITWIDTH_DEFAULT;
        ch.atten = ADC_ATTEN_DB_12;
        adc_oneshot_config_channel(h, (adc_channel_t)BATTERY_ADC_CHANNEL, &ch);
        inited = true;
    }
    static adc_oneshot_unit_handle_t unit = nullptr;
    if (unit == nullptr) {
        adc_oneshot_unit_init_cfg_t init_cfg = {};
        init_cfg.unit_id = ADC_UNIT_1;
        if (adc_oneshot_new_unit(&init_cfg, &unit) != ESP_OK) {
            return -1;
        }
        adc_oneshot_chan_cfg_t ch = {};
        ch.bitwidth = ADC_BITWIDTH_DEFAULT;
        ch.atten = ADC_ATTEN_DB_12;
        adc_oneshot_config_channel(unit, (adc_channel_t)BATTERY_ADC_CHANNEL, &ch);
    }
    int raw = 0;
    if (adc_oneshot_read(unit, (adc_channel_t)BATTERY_ADC_CHANNEL, &raw) != ESP_OK) {
        return -1;
    }
    float v = (float)raw / 4095.0f * 3300.0f * BATTERY_DIVIDER;
    return (int)v;
#else
    return -1;
#endif
}

'''
    idx = t.find("void ReportHeartbeat()")
    t = t[:idx] + helper + t[idx:]

    # 心跳体加 battery 字段
    old = '''        std::string body = "{\\"mac\\":\\"" + SystemInfo::GetMacAddress() +
                           "\\",\\"firmware\\":\\"" CONSOLE_FIRMWARE_VER "\\"}";'''
    new = '''        int _mv = ReadBatteryMv();
        char _bat[48] = "";
        if (_mv > 0) {
            int _pct = (_mv - BATTERY_EMPTY_MV) * 100 / (BATTERY_FULL_MV - BATTERY_EMPTY_MV);
            if (_pct < 0) _pct = 0;
            if (_pct > 100) _pct = 100;
            snprintf(_bat, sizeof(_bat), ",\\"battery_mv\\":%d,\\"battery_pct\\":%d", _mv, _pct);
        }
        std::string body = "{\\"mac\\":\\"" + SystemInfo::GetMacAddress() +
                           "\\",\\"firmware\\":\\"" CONSOLE_FIRMWARE_VER "\\"" + _bat + "}";'''
    if old in t:
        t = t.replace(old, new, 1)
        src.write_text(t, encoding="utf-8")
        print("dog_board.cc: 心跳已加电池字段")
    else:
        print("⚠ 心跳体未匹配")

    # 需要的头文件
    if "esp_adc/adc_oneshot.h" not in t:
        t = src.read_text(encoding="utf-8")
        t = t.replace('#include "dog_display.h"', '#include "dog_display.h"\n#include <esp_adc/adc_oneshot.h>\n#include <esp_adc/adc_cali.h>', 1)
        src.write_text(t, encoding="utf-8")
        print("dog_board.cc: 已加 ADC 头文件")
else:
    print("dog_board.cc: 已存在电池代码")
