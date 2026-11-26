#ifndef _DOG_LEDS_H_
#define _DOG_LEDS_H_

#include "led/led.h"

#include <driver/gpio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <led_strip.h>

#include <cstdint>
#include <mutex>
#include <string>

// 小慧 mini 身上的 WS2812 —— 注意是「两条链」：
//   链 A：GPIO38 → U51 → U52   （2 颗）
//   链 B：GPIO8  → U49         （1 颗，DOUT 悬空）
// 对外当作一条 3 颗的逻辑灯链使用：索引 0..count-1 走链 A，之后走链 B。
class DogLeds : public Led {
public:
    enum class Effect : uint8_t {
        kAuto = 0,
        kSolid,
        kBreathing,
        kRainbow,
        kBlink,
        kChase,
        kOff,
    };

    DogLeds(gpio_num_t gpio_a, int count_a, gpio_num_t gpio_b = GPIO_NUM_NC, int count_b = 0);
    virtual ~DogLeds();

    void OnStateChanged() override;

    void SetColor(uint8_t r, uint8_t g, uint8_t b);
    void SetPixel(int index, uint8_t r, uint8_t g, uint8_t b);
    void SetEffect(Effect effect, uint8_t r = 0, uint8_t g = 0, uint8_t b = 0, uint8_t speed = 5);
    void SetEffectByName(const std::string& name);
    void TurnOff();
    void SetAuto();

    Effect effect() const { return effect_; }
    int count() const { return count_a_ + count_b_; }
    bool ParseColor(const std::string& name, uint8_t& r, uint8_t& g, uint8_t& b);

private:
    static void TaskEntry(void* arg);
    void RunTask();
    void RefreshLocked();
    void SetAllLocked(uint8_t r, uint8_t g, uint8_t b);
    void PixelLocked(int index, uint8_t r, uint8_t g, uint8_t b);
    void HueToRgb(uint16_t hue, uint8_t& r, uint8_t& g, uint8_t& b);

    std::mutex mutex_;
    led_strip_handle_t strip_a_ = nullptr;
    led_strip_handle_t strip_b_ = nullptr;
    int count_a_ = 0;
    int count_b_ = 0;
    TaskHandle_t task_ = nullptr;
    volatile bool running_ = false;

    Effect effect_ = Effect::kAuto;
    uint8_t r_ = 0, g_ = 0, b_ = 0;
    uint8_t speed_ = 5;
    uint32_t phase_ = 0;
};

#endif  // _DOG_LEDS_H_
