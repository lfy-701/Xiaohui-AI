#include "dog_leds.h"

#include "application.h"

#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <algorithm>
#include <cctype>
#include <cstdio>

#define TAG "DogLeds"

static constexpr uint8_t kMaxBrightness = 60;
static constexpr int kTickMs = 25;

static led_strip_handle_t make_strip(gpio_num_t gpio, int count) {
    if (gpio == GPIO_NUM_NC || count <= 0) {
        return nullptr;
    }
    led_strip_config_t cfg = {};
    cfg.strip_gpio_num = gpio;
    cfg.max_leds = count;
    cfg.color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB;
    cfg.led_model = LED_MODEL_WS2812;

    led_strip_rmt_config_t rmt = {};
    rmt.resolution_hz = 10 * 1000 * 1000;

    led_strip_handle_t handle = nullptr;
    esp_err_t err = led_strip_new_rmt_device(&cfg, &rmt, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "led_strip init failed on GPIO %d: %s", (int)gpio, esp_err_to_name(err));
        return nullptr;
    }
    led_strip_clear(handle);
    ESP_LOGI(TAG, "strip on GPIO %d, %d led(s)", (int)gpio, count);
    return handle;
}

DogLeds::DogLeds(gpio_num_t gpio_a, int count_a, gpio_num_t gpio_b, int count_b)
    : count_a_(count_a), count_b_(count_b) {
    strip_a_ = make_strip(gpio_a, count_a);
    strip_b_ = make_strip(gpio_b, count_b);

    if (strip_a_ == nullptr && strip_b_ == nullptr) {
        ESP_LOGW(TAG, "no led strip available");
        return;
    }
    if (strip_a_ == nullptr) count_a_ = 0;
    if (strip_b_ == nullptr) count_b_ = 0;

    running_ = true;
    xTaskCreate(&DogLeds::TaskEntry, "dog_leds", 3072, this, 2, &task_);
}

DogLeds::~DogLeds() {
    running_ = false;
    vTaskDelay(pdMS_TO_TICKS(kTickMs * 2));
    if (task_ != nullptr) {
        vTaskDelete(task_);
        task_ = nullptr;
    }
    if (strip_a_ != nullptr) led_strip_del(strip_a_);
    if (strip_b_ != nullptr) led_strip_del(strip_b_);
}

void DogLeds::TaskEntry(void* arg) {
    static_cast<DogLeds*>(arg)->RunTask();
    vTaskDelete(nullptr);
}

void DogLeds::RefreshLocked() {
    if (strip_a_ != nullptr) led_strip_refresh(strip_a_);
    if (strip_b_ != nullptr) led_strip_refresh(strip_b_);
}

void DogLeds::PixelLocked(int index, uint8_t r, uint8_t g, uint8_t b) {
    if (index < count_a_ && strip_a_ != nullptr) {
        led_strip_set_pixel(strip_a_, index, r, g, b);
    } else if (index >= count_a_ && strip_b_ != nullptr) {
        led_strip_set_pixel(strip_b_, index - count_a_, r, g, b);
    }
}

void DogLeds::SetAllLocked(uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < count(); i++) {
        PixelLocked(i, r, g, b);
    }
}

void DogLeds::SetColor(uint8_t r, uint8_t g, uint8_t b) {
    std::lock_guard<std::mutex> lock(mutex_);
    effect_ = Effect::kSolid;
    r_ = r; g_ = g; b_ = b;
    SetAllLocked(r_, g_, b_);
    RefreshLocked();
}

void DogLeds::SetPixel(int index, uint8_t r, uint8_t g, uint8_t b) {
    if (index < 0 || index >= count()) {
        return;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    effect_ = Effect::kSolid;
    PixelLocked(index, r, g, b);
    RefreshLocked();
}

void DogLeds::SetEffect(Effect effect, uint8_t r, uint8_t g, uint8_t b, uint8_t speed) {
    std::lock_guard<std::mutex> lock(mutex_);
    effect_ = effect;
    r_ = r; g_ = g; b_ = b;
    speed_ = std::min<uint8_t>(std::max<uint8_t>(speed, 1), 10);
    phase_ = 0;
    if (effect == Effect::kOff) {
        if (strip_a_ != nullptr) led_strip_clear(strip_a_);
        if (strip_b_ != nullptr) led_strip_clear(strip_b_);
    }
}

void DogLeds::SetAuto() {
    effect_ = Effect::kAuto;
    OnStateChanged();
}

void DogLeds::TurnOff() {
    SetEffect(Effect::kOff);
}

void DogLeds::SetEffectByName(const std::string& name) {
    if (name == "rainbow") {
        SetEffect(Effect::kRainbow);
    } else if (name == "breathing" || name == "breath") {
        SetEffect(Effect::kBreathing, r_, g_, b_);
    } else if (name == "blink") {
        SetEffect(Effect::kBlink, r_, g_, b_);
    } else if (name == "chase") {
        SetEffect(Effect::kChase, r_, g_, b_);
    } else if (name == "auto") {
        SetAuto();
    } else if (name == "off") {
        TurnOff();
    } else {
        ESP_LOGW(TAG, "unknown effect: %s", name.c_str());
    }
}

bool DogLeds::ParseColor(const std::string& in, uint8_t& r, uint8_t& g, uint8_t& b) {
    std::string s;
    s.reserve(in.size());
    for (char c : in) {
        s.push_back((char)tolower((unsigned char)c));
    }

    struct Named { const char* name; uint8_t r, g, b; };
    static const Named kTable[] = {
        {"red", 255, 0, 0},      {"green", 0, 255, 0},   {"blue", 0, 0, 255},
        {"white", 255, 255, 255},{"yellow", 255, 200, 0},{"cyan", 0, 255, 255},
        {"purple", 160, 0, 255}, {"pink", 255, 60, 120},{"orange", 255, 90, 0},
        {"warm", 255, 160, 60},  {"off", 0, 0, 0},
    };
    for (const auto& n : kTable) {
        if (s == n.name) {
            r = n.r; g = n.g; b = n.b;
            return true;
        }
    }
    if (s.size() == 7 && s[0] == '#') {
        unsigned int v = 0;
        if (sscanf(s.c_str() + 1, "%06x", &v) == 1) {
            r = (v >> 16) & 0xFF;
            g = (v >> 8) & 0xFF;
            b = v & 0xFF;
            return true;
        }
    }
    return false;
}

void DogLeds::HueToRgb(uint16_t hue, uint8_t& r, uint8_t& g, uint8_t& b) {
    hue %= 360;
    uint8_t region = hue / 60;
    uint8_t rem = (uint8_t)((hue - region * 60) * 255 / 60);
    uint8_t q = 255 - rem;
    uint8_t t = rem;
    switch (region) {
        case 0: r = 255; g = t;   b = 0;   break;
        case 1: r = q;   g = 255; b = 0;   break;
        case 2: r = 0;   g = 255; b = t;   break;
        case 3: r = 0;   g = q;   b = 255; break;
        case 4: r = t;   g = 0;   b = 255; break;
        default:r = 255; g = 0;   b = q;   break;
    }
}

void DogLeds::OnStateChanged() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (effect_ != Effect::kAuto || count() == 0) {
        return;
    }

    uint8_t r = 0, g = 0, b = 0;
    switch (Application::GetInstance().GetDeviceState()) {
        case kDeviceStateIdle:       r = 0;  g = 0;  b = 8;  break;
        case kDeviceStateListening:  r = 0;  g = 12; b = 0;  break;
        case kDeviceStateSpeaking:   r = 0;  g = 10; b = 12; break;
        case kDeviceStateConnecting:
        case kDeviceStateStarting:   r = 12; g = 8;  b = 0;  break;
        default:                     return;
    }
    SetAllLocked(r, g, b);
    RefreshLocked();
}

void DogLeds::RunTask() {
    while (running_) {
        vTaskDelay(pdMS_TO_TICKS(kTickMs));

        std::lock_guard<std::mutex> lock(mutex_);
        if (count() == 0) {
            continue;
        }
        phase_++;

        switch (effect_) {
            case Effect::kAuto:
            case Effect::kSolid:
                break;

            case Effect::kOff:
                if (strip_a_ != nullptr) led_strip_clear(strip_a_);
                if (strip_b_ != nullptr) led_strip_clear(strip_b_);
                break;

            case Effect::kBreathing: {
                uint32_t period = 200 / speed_ * 10;
                if (period < 20) period = 20;
                uint32_t t = phase_ % period;
                uint32_t half = period / 2 ? period / 2 : 1;
                uint8_t level = (t < half) ? (uint8_t)(t * 255 / half)
                                           : (uint8_t)((period - t) * 255 / half);
                SetAllLocked((uint8_t)((uint32_t)r_ * level / 255),
                             (uint8_t)((uint32_t)g_ * level / 255),
                             (uint8_t)((uint32_t)b_ * level / 255));
                break;
            }

            case Effect::kRainbow: {
                int n = count();
                for (int i = 0; i < n; i++) {
                    uint16_t hue = (phase_ * (1 + speed_) / 2 + i * 360 / n) % 360;
                    uint8_t r, g, b;
                    HueToRgb(hue, r, g, b);
                    PixelLocked(i, r * kMaxBrightness / 255, g * kMaxBrightness / 255,
                                b * kMaxBrightness / 255);
                }
                break;
            }

            case Effect::kBlink: {
                bool on = (phase_ / (11 - speed_)) % 2 == 0;
                SetAllLocked(on ? r_ : 0, on ? g_ : 0, on ? b_ : 0);
                break;
            }

            case Effect::kChase: {
                int n = count();
                int pos = (phase_ * (1 + speed_) / 3) % n;
                for (int i = 0; i < n; i++) {
                    if (i == pos) {
                        PixelLocked(i, r_, g_, b_);
                    } else {
                        PixelLocked(i, r_ / 8, g_ / 8, b_ / 8);
                    }
                }
                break;
            }
        }
        RefreshLocked();
    }
}
