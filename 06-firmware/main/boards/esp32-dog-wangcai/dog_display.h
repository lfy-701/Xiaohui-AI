#ifndef _DOG_DISPLAY_H_
#define _DOG_DISPLAY_H_

#include "display/oled_display.h"
#include "dog_face.h"

#include <string>
#include <functional>
#include <esp_timer.h>

// 两种显示模式：
//   表情模式（默认，开机即显示）：整屏一张会变的狗脸
//   文字模式：显示状态和对话文字
// 长按 BOOT 键切换。
class DogDisplay : public OledDisplay {
public:
    DogDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel,
               int width, int height, bool mirror_x, bool mirror_y)
        : OledDisplay(panel_io, panel, width, height, mirror_x, mirror_y) {}


    ~DogDisplay() override {
        if (face_visible_) {
            DisplayLockGuard lock(this);
            face_.Hide();
        }
    }

    void SetChatMessage(const char* role, const char* content) override {
        last_role_ = role ? role : "";
        last_content_ = content ? content : "";
        // 用户说的话里带表情关键词时，立刻切换表情（不依赖大模型工具调用）
        if (last_role_ == "user" && content != nullptr) {
            TryTriggerFaceByText(content);
            if (command_hook_) {
                command_hook_(content);
            }
        }
        if (text_visible_) {
            OledDisplay::SetChatMessage(role, content);
        }
    }

    // 关键词 -> 表情：本地匹配，响应快
    void TryTriggerFaceByText(const std::string& text) {
        struct Rule { const char* kw; const char* expr; };
        static const Rule kRules[] = {
            {"生气", "angry"},   {"气死", "angry"},
            {"开心", "happy"},   {"高兴", "happy"},  {"笑一个", "happy"},
            {"难过", "sad"},     {"伤心", "sad"},
            {"惊讶", "surprised"}, {"吃惊", "surprised"},
            {"睡觉", "sleepy"},  {"困了", "sleepy"},
            {"喜欢", "love"},    {"爱你", "love"},
            {"眨眼", "wink"},
            {"平常", "neutral"}, {"正常", "neutral"},
        };
        for (const auto& r : kRules) {
            if (text.find(r.kw) != std::string::npos) {
                ShowTemporaryExpression(r.expr, 5000);
                return;
            }
        }
    }

    void SetEmotion(const char* emotion) override {
        if (face_visible_) {
            DisplayLockGuard lock(this);
            face_.SetEmotionName(emotion ? emotion : "");
            return;
        }
        OledDisplay::SetEmotion(emotion);
    }

    void SetStatus(const char* status) override {
        last_status_ = status ? status : "";
        if (face_visible_) {
            DisplayLockGuard lock(this);
            face_.SetStatusName(last_status_);
            return;
        }
        OledDisplay::SetStatus(status);
    }

    // 进入表情模式（开机调用一次）
    void EnterFaceMode() {
        text_visible_ = false;
        face_visible_ = true;
        OledDisplay::SetChatMessage("", "");
        DisplayLockGuard lock(this);
        face_.Show();
        face_.SetStatusName(last_status_);
    }

    // 返回切换后的状态：true = 文字模式，false = 表情模式
    bool ToggleTextVisible() {
        if (face_visible_) {
            text_visible_ = true;
            face_visible_ = false;
            {
                DisplayLockGuard lock(this);
                face_.Hide();
            }
            OledDisplay::SetChatMessage(last_role_.c_str(), last_content_.c_str());
            if (!last_status_.empty()) {
                OledDisplay::SetStatus(last_status_.c_str());
            }
        } else {
            text_visible_ = false;
            face_visible_ = true;
            OledDisplay::SetChatMessage("", "");
            DisplayLockGuard lock(this);
            face_.Show();
            face_.SetStatusName(last_status_);
        }
        return text_visible_;
    }

    // 临时表情：显示指定表情，duration 毫秒后回到状态对应表情
    void ShowTemporaryExpression(const char* name, int duration_ms = 4000) {
        if (!face_visible_) {
            EnterFaceMode();
        }
        {
            DisplayLockGuard lock(this);
            face_.SetEmotionName(name ? name : "");
        }
        if (temp_timer_ == nullptr) {
            esp_timer_create_args_t args = {};
            args.callback = [](void* arg) {
                static_cast<DogDisplay*>(arg)->RestoreBaseExpression();
            };
            args.arg = this;
            args.name = "face_restore";
            esp_timer_create(&args, &temp_timer_);
        }
        esp_timer_stop(temp_timer_);
        esp_timer_start_once(temp_timer_, (uint64_t)duration_ms * 1000);
    }

    void RestoreBaseExpression() {
        if (!face_visible_) {
            return;
        }
        DisplayLockGuard lock(this);
        face_.SetStatusName(last_status_);
    }

    // 语音指令回调（由板级设置，用于本地关键词控制舵机/灯）
    void SetCommandHook(std::function<void(const std::string&)> fn) { command_hook_ = fn; }

    bool text_visible() const { return text_visible_; }
    bool face_visible() const { return face_visible_; }

private:
    std::string last_role_;
    std::string last_content_;
    std::string last_status_;
    bool text_visible_ = true;    // 启动阶段先显示文字提示
    bool face_visible_ = false;   // 初始化完成后才切表情
    std::function<void(const std::string&)> command_hook_;
    esp_timer_handle_t temp_timer_ = nullptr;
    DogFace face_;
};

#endif  // _DOG_DISPLAY_H_
