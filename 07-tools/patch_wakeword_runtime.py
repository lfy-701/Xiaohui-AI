"""方案 C 固件侧：唤醒词支持运行时重建 + NVS 持久化。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

H = Path(r"D:\xiaozhi-esp32-2.5.2\main\audio\wake_words\custom_wake_word.h")
C = Path(r"D:\xiaozhi-esp32-2.5.2\main\audio\wake_words\custom_wake_word.cc")

# ---------------- 头文件 ----------------
h = H.read_text(encoding="utf-8")
if "ReloadWakeWords" not in h:
    anchor = "      const std::string& GetLastDetectedWakeWord() const { return last_detected_wake_word_; }"
    add = anchor + '''

      // —— 运行时唤醒词管理（控制台下发）——
      // 用拼音列表重建 MultiNet 命令表，立即生效；同时写入 NVS 供重启后恢复。
      static bool ReloadWakeWords(const std::vector<std::string>& pinyins);
      // 读取 NVS 中保存的唤醒词（空表示未设置）
      static std::vector<std::string> LoadSavedWakeWords();
      // 保存到 NVS
      static void SaveWakeWords(const std::vector<std::string>& pinyins);'''
    h = h.replace(anchor, add, 1)
    H.write_text(h, encoding="utf-8")
    print("头文件已加接口")
else:
    print("头文件已存在接口")

# ---------------- 实现 ----------------
c = C.read_text(encoding="utf-8")

if "ReloadWakeWords" in c:
    print("实现已存在，跳过")
    sys.exit(0)

# 1) 顶部加 NVS 头与静态实例指针
top_anchor = '#define TAG "CustomWakeWord"'
top_add = '''#define TAG "CustomWakeWord"

#include "settings.h"

// 当前活动的实例，供运行时重建命令表使用
static CustomWakeWord* s_active_wake_word = nullptr;
static constexpr const char* kNvsWakeWords = "wake_pinyin";'''
if top_anchor in c:
    c = c.replace(top_anchor, top_add, 1)
    print("已加 NVS 头与实例指针")

# 2) 命令注册处：优先用 NVS 保存的词表
old_push = '''        commands_.push_back({CONFIG_CUSTOM_WAKE_WORD, CONFIG_CUSTOM_WAKE_WORD_DISPLAY, "wake"});
        // 追加几个常用说法，任一句都能唤醒（MultiNet 支持一次注册多个命令词）
        commands_.push_back({"xiao hui xiao hui", "小慧小慧", "wake"});
        commands_.push_back({"hei xiao hui", "嘿小慧", "wake"});
        commands_.push_back({"xiao hui", "小慧", "wake"});'''
new_push = '''        // NVS 里有控制台下发的词表就用它，否则用编译默认值
        auto saved = LoadSavedWakeWords();
        if (!saved.empty()) {
            for (auto& p : saved) {
                commands_.push_back({p, p, "wake"});
            }
            ESP_LOGI(TAG, "使用 NVS 中的唤醒词，共 %d 个", (int)saved.size());
        } else {
            commands_.push_back({CONFIG_CUSTOM_WAKE_WORD, CONFIG_CUSTOM_WAKE_WORD_DISPLAY, "wake"});
            commands_.push_back({"xiao hui xiao hui", "小慧小慧", "wake"});
            commands_.push_back({"hei xiao hui", "嘿小慧", "wake"});
            commands_.push_back({"xiao hui", "小慧", "wake"});
        }'''
if old_push in c:
    c = c.replace(old_push, new_push, 1)
    print("已改为优先读 NVS")

# 3) Initialize 里登记活动实例
init_anchor = "    commands_.clear();"
if init_anchor in c:
    c = c.replace(init_anchor, "    commands_.clear();\n    s_active_wake_word = this;", 1)
    print("已登记活动实例")

# 4) 追加实现函数
impl = '''

// ---------------------------------------------------------------- 运行时唤醒词

std::vector<std::string> CustomWakeWord::LoadSavedWakeWords() {
    std::vector<std::string> out;
    Settings settings("wifi", false);
    std::string raw = settings.GetString(kNvsWakeWords);
    if (raw.empty()) {
        return out;
    }
    size_t start = 0;
    while (start <= raw.size()) {
        size_t pos = raw.find('|', start);
        std::string item = raw.substr(start, pos == std::string::npos ? std::string::npos : pos - start);
        // 去掉首尾空白
        while (!item.empty() && item.front() == ' ') item.erase(item.begin());
        while (!item.empty() && item.back() == ' ') item.pop_back();
        if (!item.empty()) {
            out.push_back(item);
        }
        if (pos == std::string::npos) {
            break;
        }
        start = pos + 1;
    }
    return out;
}

void CustomWakeWord::SaveWakeWords(const std::vector<std::string>& pinyins) {
    std::string joined;
    for (size_t i = 0; i < pinyins.size(); i++) {
        if (pinyins[i].empty()) {
            continue;
        }
        if (!joined.empty()) {
            joined += "|";
        }
        joined += pinyins[i];
    }
    Settings settings("wifi", true);
    settings.SetString(kNvsWakeWords, joined);
}

bool CustomWakeWord::ReloadWakeWords(const std::vector<std::string>& pinyins) {
    if (s_active_wake_word == nullptr || s_active_wake_word->multinet_ == nullptr ||
        s_active_wake_word->multinet_model_data_ == nullptr) {
        ESP_LOGW(TAG, "唤醒词引擎未就绪，稍后重试");
        return false;
    }
    if (pinyins.empty()) {
        return false;
    }

    auto* self = s_active_wake_word;

    // 重建命令表：清空 -> 逐个添加 -> 更新
    esp_mn_commands_clear();
    self->commands_.clear();
    int id = 1;
    for (const auto& p : pinyins) {
        if (p.empty()) {
            continue;
        }
        esp_mn_commands_add(id, p.c_str());
        self->commands_.push_back({p, p, "wake"});
        id++;
    }
    if (self->commands_.empty()) {
        ESP_LOGE(TAG, "没有有效的唤醒词，保持原状");
        return false;
    }
    esp_mn_commands_update();
    self->multinet_->print_active_speech_commands(self->multinet_model_data_);

    SaveWakeWords(pinyins);
    ESP_LOGI(TAG, "唤醒词已更新，共 %d 个", (int)self->commands_.size());
    return true;
}
'''

# 插到文件末尾（在最后一个 #endif 之前不行，直接追加到文件末）
c = c.rstrip() + "\n" + impl
C.write_text(c, encoding="utf-8")
print("实现已追加")
