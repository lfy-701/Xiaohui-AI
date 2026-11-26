# esp32-dog-wangcai（旺财 mini）

AI 交互小狗 —— 小智 AI 固件的板级实现。

## 硬件

| 部件 | 型号 | 接口 |
|---|---|---|
| 主控 | ESP32-S3 N16R8 | — |
| 麦克风 | INMP441 | I2S（独立） |
| 功放 | MAX98357 | I2S（独立） |
| 屏幕 | 1.3" OLED | I2C，SH1106 128×64 |
| 舵机 | 6 路 | LEDC 50Hz |
| 灯 | WS2812 × 3（串联） | 单线 RMT |

## ⚠️ 引脚必须先确认

`config.h` 里的 GPIO 目前是**占位值**，标了 `TODO 待确认`。
PCB 网表已确认的「排针脚位 → 功能网络」关系：

**下排（U14，pin1 在左）**

| pin | 网络 | pin | 网络 |
|---|---|---|---|
| 4 | MIC_WS | 12 | LEDC |
| 5 | MIC_SCK | 17 | SERVO_VE |
| 6 | MIC_SD | 18 | SERVO_HO |
| 7 | SPK_DIN | 19 | SERVO_RF |
| 8 | SPK_BCLK | 20 | SERVO_RB |
| 9 | SPK_LRC | 21 | 5VIN |
| 10 | SERVO_LF | 22 | GND |
| 11 | SERVO_LB | 1/2 | VCC / 3V3 |

**上排（U3，pin1 在右）**

| pin | 网络 |
|---|---|
| 9 | IO0 |
| 13 | RGB（WS2812 数据） |
| 16 | SDA |
| 17 | SCL |
| 1/2/22 | GND |

把上面每个 pin 对照 ESP32-S3 模块丝印换成 GPIO 编号，填回 `config.h`。

## 已实现

- 音频：INMP441 + MAX98357（SIMPLEX 双 I2S）
- 显示：SH1106 128×64 OLED
- 按键：BOOT 键切换对话 / 配网
- 舵机：6 路 LEDC，平滑插值，预设动作（站立/坐下/摇尾/摇头/前进）
- 语音控制：MCP 工具 `self.dog_action` 和 `self.set_servo`

## 待办

- [ ] 确认 GPIO 映射
- [ ] WS2812（`config.h` 里把 `DOG_USE_WS2812` 改 1 并实现 `DogLeds`）
- [ ] 网页控制台（对齐原厂固件的 `/api/control` `/api/auto` `/api/settings` `/api/custom_actions`）
- [ ] 唤醒词打断（需要 AEC 参考通道，见 xiaozhi 的 `CONFIG_USE_DEVICE_AEC`）

## 编译

```bash
python scripts/build.py esp32-dog-wangcai
# 或
idf.py set-target esp32s3 && idf.py menuconfig   # Board Type → esp32-dog-wangcai
idf.py build && idf.py flash monitor
```

需要 ESP-IDF v6.0.1+（推荐 `release/v6.1`）。
