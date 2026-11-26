#include "dog_face.h"

#include <esp_log.h>

#include <algorithm>

#define TAG "DogFace"

namespace {
constexpr int kW = 128;
constexpr int kH = 64;

// 眼睛中心
constexpr int kEyeLX = 42;
constexpr int kEyeRX = 86;
constexpr int kEyeY = 24;

// 嘴巴中心
constexpr int kMouthX = 64;
constexpr int kMouthY = 50;

lv_color_t White() { return lv_color_white(); }
lv_color_t Black() { return lv_color_black(); }

void BaseStyle(lv_obj_t* obj) {
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_CLICKABLE);
}

void Filled(lv_obj_t* obj, lv_color_t color) {
    BaseStyle(obj);
    lv_obj_set_style_bg_color(obj, color, 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
}

void Place(lv_obj_t* obj, int cx, int cy, int w, int h) {
    lv_obj_set_size(obj, w, h);
    lv_obj_set_pos(obj, cx - w / 2, cy - h / 2);
}
}  // namespace

DogFace::~DogFace() {
    if (timer_ != nullptr) {
        lv_timer_delete(timer_);
        timer_ = nullptr;
    }
    if (root_ != nullptr) {
        lv_obj_del(root_);
        root_ = nullptr;
    }
}

void DogFace::EnsureCreated() {
    // SetupUI 可能把界面重建过，导致原来的对象被清掉；这里做一次有效性检查
    if (root_ != nullptr && !lv_obj_is_valid(root_)) {
        root_ = nullptr;
        eye_l_ = eye_r_ = nullptr;
        pupil_l_ = pupil_r_ = nullptr;
        arc_l_ = arc_r_ = nullptr;
        brow_l_ = brow_r_ = nullptr;
        blush_l_ = blush_r_ = nullptr;
        mouth_arc_ = nullptr;
        mouth_fill_ = nullptr;
        heart_l_ = heart_r_ = nullptr;
        heart_l_dot_ = heart_r_dot_ = nullptr;
        zzz_ = nullptr;
        visible_ = false;
    }
    if (root_ != nullptr) {
        return;
    }

    auto screen = lv_screen_active();

    root_ = lv_obj_create(screen);
    lv_obj_set_size(root_, kW, kH);
    lv_obj_set_pos(root_, 0, 0);
    lv_obj_set_style_bg_color(root_, Black(), 0);
    lv_obj_set_style_bg_opa(root_, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(root_, 0, 0);
    lv_obj_set_style_radius(root_, 0, 0);
    BaseStyle(root_);
    lv_obj_add_flag(root_, LV_OBJ_FLAG_HIDDEN);

    // ---- 圆眼 ----
    eye_l_ = lv_obj_create(root_);
    Filled(eye_l_, White());
    eye_r_ = lv_obj_create(root_);
    Filled(eye_r_, White());

    // 瞳孔（黑点）
    pupil_l_ = lv_obj_create(eye_l_);
    Filled(pupil_l_, Black());
    pupil_r_ = lv_obj_create(eye_r_);
    Filled(pupil_r_, Black());

    // ---- 弧形眼 ----
    arc_l_ = lv_arc_create(root_);
    arc_r_ = lv_arc_create(root_);
    lv_obj_t* arcs[] = {arc_l_, arc_r_};
    for (auto* a : arcs) {
        lv_obj_set_size(a, 34, 34);
        BaseStyle(a);
        lv_obj_set_style_bg_opa(a, LV_OPA_TRANSP, 0);
        lv_obj_set_style_bg_opa(a, LV_OPA_TRANSP, LV_PART_KNOB);
        lv_obj_set_style_border_width(a, 0, LV_PART_KNOB);
        lv_obj_set_style_pad_all(a, 0, LV_PART_KNOB);
        lv_obj_set_style_arc_color(a, White(), LV_PART_MAIN);
        lv_obj_set_style_arc_color(a, White(), LV_PART_INDICATOR);
        lv_obj_set_style_arc_width(a, 6, LV_PART_MAIN);
        lv_obj_set_style_arc_width(a, 6, LV_PART_INDICATOR);
    }

    // ---- 眉毛 ----
    brow_l_ = lv_obj_create(root_);
    Filled(brow_l_, White());
    lv_obj_set_style_radius(brow_l_, 2, 0);
    brow_r_ = lv_obj_create(root_);
    Filled(brow_r_, White());
    lv_obj_set_style_radius(brow_r_, 2, 0);

    // ---- 腮红 ----
    blush_l_ = lv_obj_create(root_);
    Filled(blush_l_, White());
    lv_obj_set_style_radius(blush_l_, 2, 0);
    blush_r_ = lv_obj_create(root_);
    Filled(blush_r_, White());
    lv_obj_set_style_radius(blush_r_, 2, 0);

    // ---- 嘴巴 ----
    mouth_arc_ = lv_arc_create(root_);
    lv_obj_set_size(mouth_arc_, 46, 46);
    BaseStyle(mouth_arc_);
    lv_obj_set_style_bg_opa(mouth_arc_, LV_OPA_TRANSP, 0);
    lv_obj_set_style_bg_opa(mouth_arc_, LV_OPA_TRANSP, LV_PART_KNOB);
    lv_obj_set_style_border_width(mouth_arc_, 0, LV_PART_KNOB);
    lv_obj_set_style_pad_all(mouth_arc_, 0, LV_PART_KNOB);
    lv_obj_set_style_arc_color(mouth_arc_, White(), LV_PART_MAIN);
    lv_obj_set_style_arc_color(mouth_arc_, White(), LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(mouth_arc_, 6, LV_PART_MAIN);
    lv_obj_set_style_arc_width(mouth_arc_, 6, LV_PART_INDICATOR);

    mouth_fill_ = lv_obj_create(root_);
    Filled(mouth_fill_, White());

    // ---- 爱心 ----
    heart_l_ = lv_obj_create(root_);
    Filled(heart_l_, White());
    heart_r_ = lv_obj_create(root_);
    Filled(heart_r_, White());
    heart_l_dot_ = lv_obj_create(heart_l_);
    Filled(heart_l_dot_, White());
    lv_obj_set_style_radius(heart_l_dot_, 3, 0);
    heart_r_dot_ = lv_obj_create(heart_r_);
    Filled(heart_r_dot_, White());
    lv_obj_set_style_radius(heart_r_dot_, 3, 0);

    // ---- 睡觉的 Zz ----
    zzz_ = lv_label_create(root_);
    lv_label_set_text(zzz_, "z Z");
    lv_obj_set_style_text_color(zzz_, White(), 0);
    lv_obj_set_pos(zzz_, 96, 2);

    timer_ = lv_timer_create(TickCb, 200, this);
    Apply(expr_);
}

void DogFace::ShowPart(lv_obj_t* obj, bool show) {
    if (obj == nullptr) {
        return;
    }
    if (show) {
        lv_obj_remove_flag(obj, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
    }
}

void DogFace::ShowPair(lv_obj_t* a, lv_obj_t* b, bool show) {
    ShowPart(a, show);
    ShowPart(b, show);
}

void DogFace::SetArc(lv_obj_t* arc, int start_deg, int end_deg, int width) {
    if (arc == nullptr) {
        return;
    }
    lv_arc_set_bg_angles(arc, start_deg, end_deg);
    lv_arc_set_angles(arc, start_deg, end_deg);
    lv_obj_set_style_arc_width(arc, width, LV_PART_MAIN);
    lv_obj_set_style_arc_width(arc, width, LV_PART_INDICATOR);
}

void DogFace::Apply(Expression e) {
    expr_ = e;
    if (root_ == nullptr) {
        return;
    }

    // 先全部隐藏，再按表情打开
    ShowPair(eye_l_, eye_r_, false);
    ShowPair(pupil_l_, pupil_r_, false);
    ShowPair(arc_l_, arc_r_, false);
    ShowPair(brow_l_, brow_r_, false);
    ShowPair(blush_l_, blush_r_, false);
    ShowPair(heart_l_, heart_r_, false);
    ShowPair(heart_l_dot_, heart_r_dot_, false);
    ShowPart(mouth_arc_, false);
    ShowPart(mouth_fill_, false);
    ShowPart(zzz_, false);

    const int eye_d = 26;
    const int pupil_d = 9;

    auto round_eyes = [this](int d, int pd, int lx, int rx, int y) {
        Place(eye_l_, lx, y, d, d);
        Place(eye_r_, rx, y, d, d);
        ShowPair(eye_l_, eye_r_, true);
        lv_obj_center(pupil_l_);
        lv_obj_center(pupil_r_);
        lv_obj_set_size(pupil_l_, pd, pd);
        lv_obj_set_size(pupil_r_, pd, pd);
        ShowPair(pupil_l_, pupil_r_, true);
    };

    switch (e) {
        case kHappy: {
            Place(arc_l_, kEyeLX, kEyeY, 34, 34);
            Place(arc_r_, kEyeRX, kEyeY, 34, 34);
            SetArc(arc_l_, 200, 340, 7);
            SetArc(arc_r_, 200, 340, 7);
            ShowPair(arc_l_, arc_r_, true);

            Place(blush_l_, 16, 40, 12, 4);
            Place(blush_r_, 112, 40, 12, 4);
            ShowPair(blush_l_, blush_r_, true);

            Place(mouth_fill_, kMouthX, 50, 22, 10);
            lv_obj_set_style_radius(mouth_fill_, 5, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kWink: {
            Place(eye_l_, kEyeLX, kEyeY, 26, 26);
            ShowPart(eye_l_, true);
            lv_obj_center(pupil_l_);
            lv_obj_set_size(pupil_l_, pupil_d, pupil_d);
            ShowPart(pupil_l_, true);

            Place(arc_r_, kEyeRX, kEyeY, 34, 34);
            SetArc(arc_r_, 200, 340, 7);
            ShowPart(arc_r_, true);

            Place(blush_l_, 16, 40, 12, 4);
            Place(blush_r_, 112, 40, 12, 4);
            ShowPair(blush_l_, blush_r_, true);

            Place(mouth_fill_, kMouthX, 50, 20, 9);
            lv_obj_set_style_radius(mouth_fill_, 5, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kSurprised: {
            Place(eye_l_, kEyeLX, kEyeY, 30, 30);
            Place(eye_r_, kEyeRX, kEyeY, 30, 30);
            ShowPair(eye_l_, eye_r_, true);
            lv_obj_center(pupil_l_);
            lv_obj_center(pupil_r_);
            lv_obj_set_size(pupil_l_, 11, 11);
            lv_obj_set_size(pupil_r_, 11, 11);
            ShowPair(pupil_l_, pupil_r_, true);

            Place(mouth_fill_, kMouthX, kMouthY, 12, 12);
            lv_obj_set_style_radius(mouth_fill_, LV_RADIUS_CIRCLE, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kSleepy: {
            Place(arc_l_, kEyeLX, kEyeY, 34, 34);
            Place(arc_r_, kEyeRX, kEyeY, 34, 34);
            SetArc(arc_l_, 200, 340, 6);
            SetArc(arc_r_, 200, 340, 6);
            ShowPair(arc_l_, arc_r_, true);

            Place(mouth_fill_, kMouthX, kMouthY + 2, 16, 5);
            lv_obj_set_style_radius(mouth_fill_, 2, 0);
            ShowPart(mouth_fill_, true);
            ShowPart(zzz_, true);
            break;
        }

        case kAngry: {
            Place(eye_l_, kEyeLX, kEyeY + 3, 16, 16);
            Place(eye_r_, kEyeRX, kEyeY + 3, 16, 16);
            ShowPair(eye_l_, eye_r_, true);

            Place(brow_l_, kEyeLX + 3, kEyeY - 14, 18, 4);
            Place(brow_r_, kEyeRX - 3, kEyeY - 14, 18, 4);
            ShowPair(brow_l_, brow_r_, true);

            Place(mouth_fill_, kMouthX, kMouthY + 4, 20, 5);
            lv_obj_set_style_radius(mouth_fill_, 2, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kLove: {
            // 心形：上方两块圆角 + 下方小方块
            Place(heart_l_, kEyeLX, kEyeY - 2, 30, 24);
            lv_obj_set_style_radius(heart_l_, 11, 0);
            Place(heart_r_, kEyeRX, kEyeY - 2, 30, 24);
            lv_obj_set_style_radius(heart_r_, 11, 0);
            ShowPair(heart_l_, heart_r_, true);

            Place(heart_l_dot_, 0, 0, 12, 12);
            lv_obj_set_pos(heart_l_dot_, 9, 12);
            Place(heart_r_dot_, 0, 0, 12, 12);
            lv_obj_set_pos(heart_r_dot_, 9, 12);
            ShowPair(heart_l_dot_, heart_r_dot_, true);

            Place(mouth_fill_, kMouthX, 50, 20, 9);
            lv_obj_set_style_radius(mouth_fill_, 5, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kListening: {
            round_eyes(28, 10, kEyeLX, kEyeRX, kEyeY);
            Place(mouth_fill_, kMouthX, kMouthY, 18, 8);
            lv_obj_set_style_radius(mouth_fill_, 4, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kSpeaking: {
            round_eyes(26, 9, kEyeLX, kEyeRX, kEyeY);
            Place(mouth_fill_, kMouthX, kMouthY, 26, 12);
            lv_obj_set_style_radius(mouth_fill_, 6, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kThinking: {
            Place(eye_l_, kEyeLX, kEyeY, 28, 28);
            Place(eye_r_, kEyeRX, kEyeY, 18, 18);
            ShowPair(eye_l_, eye_r_, true);
            lv_obj_center(pupil_l_);
            lv_obj_center(pupil_r_);
            lv_obj_set_size(pupil_l_, 10, 10);
            lv_obj_set_size(pupil_r_, 7, 7);
            ShowPair(pupil_l_, pupil_r_, true);

            Place(mouth_fill_, 74, kMouthY, 16, 5);
            lv_obj_set_style_radius(mouth_fill_, 2, 0);
            ShowPart(mouth_fill_, true);
            break;
        }

        case kSad: {
            round_eyes(22, 8, kEyeLX, kEyeRX, kEyeY);
            Place(brow_l_, kEyeLX - 4, kEyeY - 12, 18, 4);
            Place(brow_r_, kEyeRX + 4, kEyeY - 12, 18, 4);
            ShowPair(brow_l_, brow_r_, true);

            Place(mouth_arc_, kMouthX, 52, 34, 34);
            SetArc(mouth_arc_, 20, 160, 5);
            ShowPart(mouth_arc_, true);
            break;
        }

        case kMusic: {
            // 频谱眼：每侧 3 根柱，底边对齐，高低随时间跳动
            const int bottom = 44;
            const int heights[6] = {18, 30, 12, 26, 16, 34};

            lv_obj_t* bars[6] = {eye_l_, pupil_l_, brow_l_, eye_r_, pupil_r_, brow_r_};
            const int xs[6] = {26, 38, 50, 78, 90, 102};

            for (int i = 0; i < 6; i++) {
                int hgt = heights[i];
                Place(bars[i], xs[i], bottom - hgt / 2, 7, hgt);
                lv_obj_set_style_radius(bars[i], 3, 0);
                ShowPart(bars[i], true);
            }

            // 微笑的嘴
            Place(mouth_arc_, kMouthX, 54, 30, 30);
            SetArc(mouth_arc_, 20, 160, 4);
            ShowPart(mouth_arc_, true);
            break;
        }

        case kNeutral:
        default: {
            round_eyes(eye_d, pupil_d, kEyeLX, kEyeRX, kEyeY);
            Place(mouth_fill_, kMouthX, kMouthY, 22, 5);
            lv_obj_set_style_radius(mouth_fill_, 2, 0);
            ShowPart(mouth_fill_, true);
            break;
        }
    }
}

void DogFace::SetExpression(Expression e) {
    EnsureCreated();
    Apply(e);
}

void DogFace::SetEmotionName(const std::string& name) {
    std::string n = name;
    std::transform(n.begin(), n.end(), n.begin(), ::tolower);
    auto has = [&n](const char* kw) { return n.find(kw) != std::string::npos; };

    if (has("happy") || has("joy") || has("开心") || has("高兴")) {
        SetExpression(kHappy);
    } else if (has("wink") || has("眨眼")) {
        SetExpression(kWink);
    } else if (has("sad") || has("cry") || has("难过") || has("伤心")) {
        SetExpression(kSad);
    } else if (has("angry") || has("mad") || has("生气")) {
        SetExpression(kAngry);
    } else if (has("surprised") || has("shock") || has("惊讶")) {
        SetExpression(kSurprised);
    } else if (has("sleepy") || has("tired") || has("困") || has("睡")) {
        SetExpression(kSleepy);
    } else if (has("music") || has("听歌") || has("唱歌") || has("享受")) {
        SetExpression(kMusic);
    } else if (has("love") || has("like") || has("喜欢")) {
        SetExpression(kLove);
    } else if (has("thinking") || has("think") || has("思考")) {
        SetExpression(kThinking);
    } else {
        SetExpression(kNeutral);
    }
}

void DogFace::SetStatusName(const std::string& status) {
    if (status.find("聆听") != std::string::npos || status.find("listen") != std::string::npos) {
        SetExpression(kListening);
    } else if (status.find("说话") != std::string::npos || status.find("speak") != std::string::npos) {
        SetExpression(kSpeaking);
    } else if (status.find("思考") != std::string::npos || status.find("think") != std::string::npos) {
        SetExpression(kThinking);
    } else if (status.find("连接") != std::string::npos || status.find("connect") != std::string::npos) {
        SetExpression(kSleepy);
    } else {
        SetExpression(kNeutral);
    }
}

void DogFace::Show() {
    EnsureCreated();
    lv_obj_remove_flag(root_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(root_);
    visible_ = true;
    Apply(expr_);
}

void DogFace::Hide() {
    visible_ = false;
    if (root_ != nullptr) {
        lv_obj_add_flag(root_, LV_OBJ_FLAG_HIDDEN);
    }
}

void DogFace::TickCb(lv_timer_t* timer) {
    auto* self = static_cast<DogFace*>(lv_timer_get_user_data(timer));
    if (self != nullptr && self->visible_) {
        self->TickCbImpl();
    }
}

void DogFace::TickCbImpl() {
    tick_++;

    // 保险：每约 2 秒把表情层提到最前面，
    // 避免状态栏 / 通知等文字对象被重新绘制到表情之上。
    if (tick_ % 10 == 0 && root_ != nullptr && lv_obj_is_valid(root_)) {
        lv_obj_move_foreground(root_);
    }

    // 听音乐：频谱柱按节奏跳动
    if (expr_ == kMusic) {
        static const int frames[4][6] = {
            {14, 28, 10, 24, 34, 18},
            {26, 12, 32, 14, 20, 30},
            {10, 34, 20, 30, 12, 26},
            {30, 16, 26, 10, 28, 14},
        };
        const int bottom = 44;
        lv_obj_t* bars[6] = {eye_l_, pupil_l_, brow_l_, eye_r_, pupil_r_, brow_r_};
        const int xs[6] = {26, 38, 50, 78, 90, 102};
        int f = (tick_ / 3) % 4;
        for (int i = 0; i < 6; i++) {
            int hgt = frames[f][i];
            Place(bars[i], xs[i], bottom - hgt / 2, 7, hgt);
        }
    }

    // 说话时嘴巴开合
    if (expr_ == kSpeaking) {
        int h = (tick_ % 4 < 2) ? 8 : 16;
        Place(mouth_fill_, kMouthX, kMouthY, 26, h);
    }

    // 平常状态每约 3 秒眨一次
    if (blink_ticks_ > 0) {
        blink_ticks_--;
        if (blink_ticks_ == 0) {
            Apply(expr_);
        }
        return;
    }
    if (tick_ % 15 == 0 && (expr_ == kNeutral || expr_ == kListening)) {
        blink_ticks_ = 1;
        ShowPair(eye_l_, eye_r_, false);
        ShowPair(pupil_l_, pupil_r_, false);
        Place(arc_l_, kEyeLX, kEyeY, 34, 34);
        Place(arc_r_, kEyeRX, kEyeY, 34, 34);
        SetArc(arc_l_, 200, 340, 5);
        SetArc(arc_r_, 200, 340, 5);
        ShowPair(arc_l_, arc_r_, true);
    }
}
