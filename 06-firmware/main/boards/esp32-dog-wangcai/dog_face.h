#ifndef _DOG_FACE_H_
#define _DOG_FACE_H_

#include <lvgl.h>

#include <string>

// 128x64 单色 OLED 上的机器人狗脸（参考主流表情设计）：
//   大圆眼 + 瞳孔高光 + 弧线嘴 + 腮红，
//   开心 / 眨眼 / 惊讶 / 睡觉 / 生气 / 喜欢 各有独立画法。
// 全部用 LVGL 图元拼出来，不依赖表情字库。
class DogFace {
public:
    enum Expression {
        kNeutral,    // 平常
        kHappy,      // 开心
        kWink,       // 眨眼
        kSurprised,  // 惊讶
        kSleepy,     // 睡觉
        kAngry,      // 生气
        kLove,       // 喜欢
        kListening,  // 正在听
        kSpeaking,   // 正在说
        kThinking,   // 思考
        kSad,        // 难过
        kMusic,      // 听音乐（频谱眼）
    };

    DogFace() = default;
    ~DogFace();

    void Show();
    void Hide();
    bool visible() const { return visible_; }

    void SetExpression(Expression e);
    void SetEmotionName(const std::string& name);
    void SetStatusName(const std::string& status);

    Expression expression() const { return expr_; }

private:
    void EnsureCreated();
    void Apply(Expression e);
    void ShowPart(lv_obj_t* obj, bool show);
    void ShowPair(lv_obj_t* a, lv_obj_t* b, bool show);
    void SetArc(lv_obj_t* arc, int start_deg, int end_deg, int width);
    void TickCbImpl();
    static void TickCb(lv_timer_t* timer);

    lv_obj_t* root_ = nullptr;

    // 圆眼（白圆）+ 瞳孔（黑点）
    lv_obj_t* eye_l_ = nullptr;
    lv_obj_t* eye_r_ = nullptr;
    lv_obj_t* pupil_l_ = nullptr;
    lv_obj_t* pupil_r_ = nullptr;

    // 弧形眼（开心 / 睡觉 / 眨眼）
    lv_obj_t* arc_l_ = nullptr;
    lv_obj_t* arc_r_ = nullptr;

    // 眉毛
    lv_obj_t* brow_l_ = nullptr;
    lv_obj_t* brow_r_ = nullptr;

    // 腮红
    lv_obj_t* blush_l_ = nullptr;
    lv_obj_t* blush_r_ = nullptr;

    // 嘴巴：弧线（笑 / 撇嘴）与实心（张嘴 / o 形）
    lv_obj_t* mouth_arc_ = nullptr;
    lv_obj_t* mouth_fill_ = nullptr;

    // 爱心眼（喜欢）：两个圆 + 下方一块方块拼成心形
    lv_obj_t* heart_l_ = nullptr;
    lv_obj_t* heart_r_ = nullptr;
    lv_obj_t* heart_l_dot_ = nullptr;
    lv_obj_t* heart_r_dot_ = nullptr;

    // 睡觉的 Zz
    lv_obj_t* zzz_ = nullptr;

    lv_timer_t* timer_ = nullptr;
    Expression expr_ = kNeutral;
    bool visible_ = false;
    int tick_ = 0;
    int blink_ticks_ = 0;
};

#endif  // _DOG_FACE_H_
