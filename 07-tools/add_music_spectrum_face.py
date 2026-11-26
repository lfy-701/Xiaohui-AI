"""固件：新增「频谱眼」表情 kMusic（播放音乐时用），带节奏动画。"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FW = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai")

# ---------- 1) 头文件加枚举 ----------
H = FW / "dog_face.h"
h = H.read_text(encoding="utf-8")
if "kMusic" not in h:
    h = h.replace(
        "        kSad,        // 难过",
        "        kSad,        // 难过\n        kMusic,      // 听音乐（频谱眼）",
        1,
    )
    H.write_text(h, encoding="utf-8")
    print("dog_face.h: 已加 kMusic")

# ---------- 2) 绘制逻辑 ----------
C = FW / "dog_face.cc"
c = C.read_text(encoding="utf-8")

if "case kMusic" not in c:
    # 复用已有图元：每侧 3 根柱（eye/pupil/brow），底边对齐，形成 6 柱频谱
    case_code = '''        case kMusic: {
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

'''
    idx = c.find("        case kNeutral:")
    if idx < 0:
        print("⚠ 未找到插入点")
        sys.exit(1)
    c = c[:idx] + case_code + c[idx:]
    print("dog_face.cc: 已加 kMusic 绘制")

# ---------- 3) 动画：频谱跳动 ----------
old_tick = """    // 说话时嘴巴开合
    if (expr_ == kSpeaking) {"""
new_tick = """    // 听音乐：频谱柱按节奏跳动
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
    if (expr_ == kSpeaking) {"""
if old_tick in c:
    c = c.replace(old_tick, new_tick, 1)
    print("dog_face.cc: 已加频谱动画")
else:
    print("⚠ 未匹配动画插入点")

# ---------- 4) 表情名映射 ----------
old_map = '''      } else if (has("thinking") || has("think") || has("思考")) {'''
new_map = '''      } else if (has("music") || has("听歌") || has("唱歌") || has("享受")) {
          SetExpression(kMusic);
      } else if (has("thinking") || has("think") || has("思考")) {'''
if old_map in c:
    c = c.replace(old_map, new_map, 1)
    print("dog_face.cc: 已加 music 名称映射")
else:
    print("⚠ 未匹配名称映射")

C.write_text(c, encoding="utf-8")

# ---------- 5) 语音服务：音乐表情改为 music ----------
V = Path(r"C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server\core\api\console_handler.py")
v = V.read_text(encoding="utf-8")
if 'MUSIC_EMOTION = "love"' in v:
    v = v.replace('MUSIC_EMOTION = "love"', 'MUSIC_EMOTION = "music"', 1)
    V.write_text(v, encoding="utf-8")
    print("语音服务: 音乐表情 love -> music")
