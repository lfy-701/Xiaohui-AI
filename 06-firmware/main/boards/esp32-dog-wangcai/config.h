#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

// ============================================================================
//  小慧 mini（AI 小狗）板级配置
//
//  引脚映射来源：ESP32-S3-N16R8 模块丝印 + PCB 网表交叉验证
//  校验锚点（三重一致，可信）：
//    U3-9  = IO0 网络  -> GPIO0      （网表网络名就叫 IO0）
//    U3-16 = SDA 网络  -> GPIO41     （固件二进制反汇编确认 sda_io_num=41）
//    U3-17 = SCL 网络  -> GPIO42     （固件二进制反汇编确认 scl_io_num=42）
// ============================================================================

// ---------------- 音频 ----------------
// 麦克风 INMP441 与功放 MAX98357 是两套独立 I2S → SIMPLEX
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000
#define AUDIO_I2S_METHOD_SIMPLEX

// INMP441（PCB 网络：MIC_WS / MIC_SCK / MIC_SD）
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_4
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_5
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_6

// MAX98357（PCB 网络：SPK_BCLK / SPK_LRC / SPK_DIN）
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_15
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_16
#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_7

// ---------------- 显示 ----------------
// 1.3" OLED，I2C（PCB 网络：SDA / SCL），地址 0x3C
#define DISPLAY_SDA_PIN GPIO_NUM_41
#define DISPLAY_SCL_PIN GPIO_NUM_42
#define DISPLAY_WIDTH   128
#define DISPLAY_HEIGHT  64
#define DISPLAY_MIRROR_X false
#define DISPLAY_MIRROR_Y false
#define SH1106

// ---------------- 舵机 ----------------
// 6 路（PCB 网络：SERVO_LF / SERVO_LB / SERVO_RF / SERVO_RB / SERVO_VE / SERVO_HO）
#define SERVO_LF_PIN GPIO_NUM_17
#define SERVO_LB_PIN GPIO_NUM_18
#define SERVO_RF_PIN GPIO_NUM_13
#define SERVO_RB_PIN GPIO_NUM_14
#define SERVO_VE_PIN GPIO_NUM_11
#define SERVO_HO_PIN GPIO_NUM_12

#define SERVO_COUNT           6

#define SERVO_MIN_PULSE_US    500
#define SERVO_MAX_PULSE_US    2500
#define SERVO_FREQ_HZ         50
#define SERVO_DEFAULT_ANGLE   90

// ---------------- 舵机方向 / 微调 ----------------
// 左右两侧腿机械上是镜像装的，同一条指令会让它们朝相反方向转。
// 这里用 +1 / -1 把它折算成统一的「物理正方向」。
// 校准方法：说「测试腿」逐条看，哪条反了就把对应 DIR 改成相反值。
#define SERVO_LF_DIR    1     // 左前
#define SERVO_LB_DIR    1     // 左后
#define SERVO_RF_DIR   -1     // 右前
#define SERVO_RB_DIR   -1     // 右后
#define SERVO_VE_DIR    1     // 竖直
#define SERVO_HO_DIR    1     // 头部

// 中位微调（装配误差，单位：度）；装歪了就靠这个补
#define SERVO_LF_TRIM   0
#define SERVO_LB_TRIM   0
#define SERVO_RF_TRIM   0
#define SERVO_RB_TRIM   0
#define SERVO_VE_TRIM   0
#define SERVO_HO_TRIM   0

// ---------------- 步态参数 ----------------
#define SERVO_WALK_AMPLITUDE   25    // 摆幅（度），太大容易绊倒，先 20~30
#define SERVO_WALK_PERIOD_MS   600   // 一个完整步态周期

// ---------------- WS2812 ----------------
// 注意：3 颗灯分成两条独立链（按 PCB 网络核对）
//   链 A：GPIO38 -> U51 -> U52   （2 颗，网络 RGB / RGB_D）
//   链 B：GPIO8  -> U49          （1 颗，网络 LEDC，DOUT 悬空）
#define DOG_USE_WS2812   1
#define WS2812_GPIO      GPIO_NUM_38
#define WS2812_COUNT     2
#define WS2812_GPIO_2    GPIO_NUM_8
#define WS2812_COUNT_2   1

// ---------------- 按键 ----------------
#define BOOT_BUTTON_GPIO GPIO_NUM_0

#endif // _BOARD_CONFIG_H_
