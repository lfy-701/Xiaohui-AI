#include "servo_controller.h"

#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <algorithm>
#include <cmath>

static const char* TAG = "ServoController";

// 腿的方向系数：左右两侧机械上是镜像的，这里把它折算成「物理正方向」
// 配置在 config.h 里，可用 self.leg_move 逐条校准
static const int kDir[SERVO_COUNT] = {
    SERVO_LF_DIR, SERVO_LB_DIR, SERVO_RF_DIR, SERVO_RB_DIR,
    SERVO_VE_DIR, SERVO_HO_DIR,
};

// 每路的中位微调（机械装配误差补偿）
static const int kTrim[SERVO_COUNT] = {
    SERVO_LF_TRIM, SERVO_LB_TRIM, SERVO_RF_TRIM, SERVO_RB_TRIM,
    SERVO_VE_TRIM, SERVO_HO_TRIM,
};

// LEDC: 50Hz, 13bit → 周期 20ms
// 0.5ms ≈ 332 counts, 2.5ms ≈ 1023 counts
uint32_t ServoController::AngleToDuty(int degrees) {
    int angle = std::min(std::max(degrees, 0), 180);
    return static_cast<uint32_t>(((angle / 180.0) * 2.0 + 0.5) * 8191 / 20.0);
}

void ServoController::Initialize() {
    if (initialized_) {
        return;
    }

    ledc_timer_config_t timer_cfg = {};
    timer_cfg.speed_mode = LEDC_LOW_SPEED_MODE;
    timer_cfg.duty_resolution = LEDC_TIMER_13_BIT;
    timer_cfg.timer_num = LEDC_TIMER_0;
    timer_cfg.freq_hz = SERVO_FREQ_HZ;
    timer_cfg.clk_cfg = LEDC_AUTO_CLK;
    ESP_ERROR_CHECK(ledc_timer_config(&timer_cfg));

    for (auto& ch : channels_) {
        ledc_channel_config_t ch_cfg = {};
        ch_cfg.gpio_num = ch.gpio;
        ch_cfg.speed_mode = LEDC_LOW_SPEED_MODE;
        ch_cfg.channel = ch.channel;
        ch_cfg.intr_type = LEDC_INTR_DISABLE;
        ch_cfg.timer_sel = LEDC_TIMER_0;
        ch_cfg.duty = AngleToDuty(ch.angle);
        ch_cfg.hpoint = 0;
        ESP_ERROR_CHECK(ledc_channel_config(&ch_cfg));
    }

    initialized_ = true;
    ESP_LOGI(TAG, "initialized %d servos", SERVO_COUNT);
}

void ServoController::Apply(ServoId id, int degrees) {
    int idx = static_cast<int>(id);
    if (idx < 0 || idx >= SERVO_COUNT) {
        return;
    }
    auto& ch = channels_[idx];
    ch.angle = std::min(std::max(degrees, 0), 180);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, ch.channel, AngleToDuty(ch.angle));
    ledc_update_duty(LEDC_LOW_SPEED_MODE, ch.channel);
}

void ServoController::SetAngle(ServoId id, int degrees) {
    Apply(id, degrees + kTrim[static_cast<int>(id)]);
}

int ServoController::GetAngle(ServoId id) const {
    int idx = static_cast<int>(id);
    if (idx < 0 || idx >= SERVO_COUNT) {
        return 0;
    }
    return channels_[idx].angle - kTrim[idx];
}

void ServoController::Nudge(ServoId id, int delta_degrees) {
    int cur = GetAngle(id);
    int next = std::min(std::max(cur + delta_degrees, 0), 180);
    SetAngle(id, next);
    ESP_LOGI(TAG, "leg %d -> %d deg", static_cast<int>(id), next);
}

void ServoController::MoveTo(ServoId id, int degrees, int duration_ms) {
    int idx = static_cast<int>(id);
    if (idx < 0 || idx >= SERVO_COUNT) {
        return;
    }
    int from = GetAngle(id);
    int to = std::min(std::max(degrees, 0), 180);
    if (duration_ms <= 0 || from == to) {
        SetAngle(id, to);
        return;
    }
    const int step_ms = 20;
    int steps = std::max(1, duration_ms / step_ms);
    for (int i = 1; i <= steps; i++) {
        SetAngle(id, from + (to - from) * i / steps);
        vTaskDelay(pdMS_TO_TICKS(step_ms));
    }
}

void ServoController::MoveAll(const std::array<int, 6>& target, int duration_ms) {
    std::array<int, 6> from;
    for (int i = 0; i < 6; i++) {
        from[i] = GetAngle(static_cast<ServoId>(i));
    }
    const int step_ms = 20;
    int steps = std::max(1, duration_ms / step_ms);
    for (int s = 1; s <= steps; s++) {
        for (int i = 0; i < 6; i++) {
            SetAngle(static_cast<ServoId>(i), from[i] + (target[i] - from[i]) * s / steps);
        }
        vTaskDelay(pdMS_TO_TICKS(step_ms));
    }
}

void ServoController::Stand() {
    MoveAll({90, 90, 90, 90, 90, 90}, 500);
}

void ServoController::Sit() {
    // 后腿收、前腿撑
    MoveAll({90, 50, 90, 121, 90, 90}, 700);
}

void ServoController::Wag(int times) {
    for (int i = 0; i < times; i++) {
        MoveTo(ServoId::kHead, 120, 160);
        MoveTo(ServoId::kHead, 60, 160);
    }
    MoveTo(ServoId::kHead, 90, 160);
}

void ServoController::ShakeHead(int times) {
    for (int i = 0; i < times; i++) {
        MoveTo(ServoId::kVertical, 115, 180);
        MoveTo(ServoId::kVertical, 65, 180);
    }
    MoveTo(ServoId::kVertical, 90, 180);
}

// 对角小跑（trot）：
//   LF + RB 同相，RF + LB 反相
//   每 tick 用正弦算角度，方向系数把左右镜像折算成同一个物理方向
void ServoController::WalkForward(int steps) {
    if (!initialized_) {
        return;
    }

    const float amp = SERVO_WALK_AMPLITUDE;      // 摆幅（度）
    const int period_ms = SERVO_WALK_PERIOD_MS;  // 一个完整步态周期
    const int tick_ms = 20;
    const float two_pi = 6.2831853f;

    const int total_ms = std::max(1, steps) * period_ms;
    // 相位偏移：LF/RB = 0，RF/LB = π
    const float kOff[4] = {0.0f, 3.1415926f, 3.1415926f, 0.0f};  // LF, LB, RF, RB

    for (int t = 0; t < total_ms; t += tick_ms) {
        float ph = two_pi * (float)t / (float)period_ms;
        for (int i = 0; i < 4; i++) {
            float s = sinf(ph + kOff[i]);
            int angle = 90 + kDir[i] * (int)(s * amp);
            SetAngle(static_cast<ServoId>(i), angle);
        }
        vTaskDelay(pdMS_TO_TICKS(tick_ms));
    }

    // 收尾回中位
    MoveAll({90, 90, 90, 90, GetAngle(ServoId::kVertical), GetAngle(ServoId::kHead)}, 300);
}

// 逐条腿点动，用于校准方向，不会误伤其他腿
void ServoController::LegTest() {
    static const char* names[4] = {"左前", "左后", "右前", "右后"};
    for (int i = 0; i < 4; i++) {
        ESP_LOGI(TAG, "test %s leg", names[i]);
        SetAngle(static_cast<ServoId>(i), 90 + 25 * kDir[i]);
        vTaskDelay(pdMS_TO_TICKS(500));
        SetAngle(static_cast<ServoId>(i), 90);
        vTaskDelay(pdMS_TO_TICKS(300));
    }
}

// ---------------------------------------------------------------- 新增动作

void ServoController::WalkBackward(int steps) {
    // 后退：与前进同相位但反向，用负振幅实现
    if (!initialized_) {
        return;
    }
    const float amp = SERVO_WALK_AMPLITUDE;
    const int period_ms = SERVO_WALK_PERIOD_MS;
    const int tick_ms = 20;
    const float two_pi = 6.2831853f;
    const int total_ms = std::max(1, steps) * period_ms;
    const float kOff[4] = {0.0f, 3.1415926f, 3.1415926f, 0.0f};

    for (int t = 0; t < total_ms; t += tick_ms) {
        float phase = two_pi * (float)(t % period_ms) / (float)period_ms;
        for (int leg = 0; leg < 4; leg++) {
            float v = 90.0f - amp * sinf(phase + kOff[leg]);
            Apply((ServoId)leg, (int)v);
        }
        vTaskDelay(pdMS_TO_TICKS(tick_ms));
    }
    Stand();
}

void ServoController::TurnLeft(int steps) {
    // 左转：左侧腿后撤、右侧腿前推（差速）
    if (!initialized_) {
        return;
    }
    for (int i = 0; i < std::max(1, steps); i++) {
        MoveAll({60, 60, 120, 120, 90, 90}, 320);
        MoveAll({120, 120, 60, 60, 90, 90}, 320);
    }
    Stand();
}

void ServoController::TurnRight(int steps) {
    if (!initialized_) {
        return;
    }
    for (int i = 0; i < std::max(1, steps); i++) {
        MoveAll({120, 120, 60, 60, 90, 90}, 320);
        MoveAll({60, 60, 120, 120, 90, 90}, 320);
    }
    Stand();
}

void ServoController::Dance(int cycles) {
    // 跳舞：摇尾 + 摇头 + 左右摆身
    if (!initialized_) {
        return;
    }
    for (int i = 0; i < std::max(1, cycles); i++) {
        MoveAll({70, 70, 110, 110, 90, 60}, 170);
        Wag(2);
        MoveAll({110, 110, 70, 70, 90, 120}, 170);
        ShakeHead(2);
    }
    Stand();
}

void ServoController::LieDown() {
    // 趴下：前腿前伸压低、后腿收拢
    if (!initialized_) {
        return;
    }
    MoveAll({50, 50, 121, 121, 90, 90}, 800);
}

void ServoController::Sleep() {
    LieDown();
    MoveTo(ServoId::kHead, 60, 600);
}

void ServoController::WakeUp() {
    MoveTo(ServoId::kHead, 90, 300);
    Stand();
}