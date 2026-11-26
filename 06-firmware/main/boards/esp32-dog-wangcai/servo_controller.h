#ifndef _SERVO_CONTROLLER_H_
#define _SERVO_CONTROLLER_H_

#include <driver/gpio.h>
#include <driver/ledc.h>

#include <array>
#include <cstdint>

#include "config.h"

// 六路舵机命名（对应 PCB 网络 SERVO_LF / LB / RF / RB / VE / HO）
enum class ServoId : uint8_t {
    kLeftFront = 0,
    kLeftBack,
    kRightFront,
    kRightBack,
    kVertical,
    kHead,
    kCount
};

class ServoController {
public:
    ServoController() = default;
    ~ServoController() = default;

    // 初始化 LEDC 定时器与六路通道
    void Initialize();

    // 立刻设置单路角度（0~180），带限位
    void SetAngle(ServoId id, int degrees);

    // 平滑移动到目标角度，duration_ms 为过渡时间
    void MoveTo(ServoId id, int degrees, int duration_ms = 300);

    // 六路一起平滑移动
    void MoveAll(const std::array<int, 6>& target, int duration_ms = 400);

    // 读取当前逻辑角度
    int GetAngle(ServoId id) const;

    // ---- 预设动作 ----
    void Stand();                   // 站立
    void Sit();                     // 坐下
    void Wag(int times = 3);        // 摇尾巴
    void ShakeHead(int times = 2);  // 摇头
    void WalkForward(int steps = 4);
    void WalkBackward(int steps = 4);
    void TurnLeft(int steps = 3);      // 左转
    void TurnRight(int steps = 3);     // 右转
    void Dance(int cycles = 2);        // 跳舞
    void LieDown();                    // 趴下
    void Sleep();                      // 睡觉（趴下 + 低头）
    void WakeUp();                     // 起身

    // 相对点动，用于校准单条腿（delta 为正负角度）
    void Nudge(ServoId id, int delta_degrees);

    // 逐条腿依次点动，用来确认哪条腿是哪个、方向对不对
    void LegTest();

private:
    struct Channel {
        ledc_channel_t channel;
        gpio_num_t gpio;
        int angle;
    };

    static uint32_t AngleToDuty(int degrees);
    void Apply(ServoId id, int degrees);

    std::array<Channel, 6> channels_ = {{
        {LEDC_CHANNEL_0, SERVO_LF_PIN, SERVO_DEFAULT_ANGLE},
        {LEDC_CHANNEL_1, SERVO_LB_PIN, SERVO_DEFAULT_ANGLE},
        {LEDC_CHANNEL_2, SERVO_RF_PIN, SERVO_DEFAULT_ANGLE},
        {LEDC_CHANNEL_3, SERVO_RB_PIN, SERVO_DEFAULT_ANGLE},
        {LEDC_CHANNEL_4, SERVO_VE_PIN, SERVO_DEFAULT_ANGLE},
        {LEDC_CHANNEL_5, SERVO_HO_PIN, SERVO_DEFAULT_ANGLE},
    }};
    bool initialized_ = false;
};

#endif  // _SERVO_CONTROLLER_H_
