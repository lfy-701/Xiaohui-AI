#include "wifi_board.h"
#include "display/oled_display.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "mcp_server.h"
#include "audio/wake_words/custom_wake_word.h"
#include "servo_controller.h"
#include "dog_display.h"
#include <cstdlib>
#include "codecs/no_audio_codec.h"

#if DOG_USE_WS2812
#include "dog_leds.h"
#endif

#include <esp_log.h>
#include <driver/i2c_master.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_vendor.h>
#include <cJSON.h>
#include <cstring>

#include "system_info.h"
#include "settings.h"

#ifdef SH1106
#include <esp_lcd_panel_sh1106.h>

// 本地私有配置（不入库）：真实控制台地址与设备令牌
#if __has_include("config_local.h")
#include "config_local.h"
#endif
#endif

#define TAG "DogBoard"

// ---- 控制台接入 ----
// 设备开机后向控制台注册，拿到 6 位激活码显示在屏幕上；
// 之后每 30 秒心跳一次，顺便取回自己绑定的智能体配置。
//
// 地址列表：按顺序尝试，连不上自动换下一个。
// 电脑换网络（手机热点 / 校园网）时，不用重新编译。
//   ⚠️ 不能用 100.x.x.x —— 那是 Tailscale 网段，ESP32 不在 tailnet 里，没有路由。
// 控制台地址的「开发兜底值」。
// 正式使用时应在配网页面「Advanced → 自定义 OTA 地址」里填自己的服务器，
// 设备会优先读取那个配置（存 NVS wifi/ota_url），这里的地址只是没配时的后备。
static const char* kConsoleHosts[] = {
    "http://192.168.1.100",   // 示例：改成你自己的局域网地址
    "http://<你的服务器局域网IP>",  // 备用：本机控制台地址
};
static const int kConsoleHostCount = sizeof(kConsoleHosts) / sizeof(kConsoleHosts[0]);
static int s_console_host_index = 0;

// 必须与控制台服务端环境变量 DEVICE_TOKEN 一致；此处填占位符，请自行替换
#ifndef CONSOLE_DEVICE_TOKEN
#define CONSOLE_DEVICE_TOKEN "CHANGE_ME_DEVICE_TOKEN"
#endif
#define CONSOLE_FIRMWARE_VER "2.5.3"
#define CONSOLE_HEARTBEAT_MS 400    // 0.4 秒一次：连接/动作指令更快落地

// 小慧 mini —— AI 交互小狗
// 外设：INMP441(麦克风) / MAX98357(功放) / SH1106 128x64(OLED) / 6 路舵机 / 3 颗 WS2812
class DogBoard : public WifiBoard {
private:
    i2c_master_bus_handle_t display_i2c_bus_ = nullptr;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    DogDisplay* display_ = nullptr;
    Button boot_button_;
    ServoController servo_;

    // 往控制台 POST 一个 JSON，成功返回 true 并把响应放在 resp
    // 失败会自动切换到下一个候选地址（热点 / 校园网）
    // 控制台地址来源优先级：
    //   1) 配网页面「Advanced → Custom OTA URL」里填的地址（存 NVS wifi/ota_url）
    //   2) 编译时的候选列表（仅作开发兜底）
    // 这样每个用户配自己的服务器，不用重新编译固件。
    std::string ConsoleBase() {
        Settings settings("wifi", false);
        std::string ota_url = settings.GetString("ota_url");
        if (ota_url.empty()) {
            return kConsoleHosts[s_console_host_index];
        }
        // 去掉末尾的 /ota/ 或 /ota，只留主机部分
        for (const char* suffix : {"/ota/", "/ota", "/"}) {
            size_t n = strlen(suffix);
            if (ota_url.size() >= n && ota_url.compare(ota_url.size() - n, n, suffix) == 0) {
                ota_url.erase(ota_url.size() - n);
                break;
            }
        }
        return ota_url;
    }

    bool ConsolePost(const std::string& path, const std::string& body, std::string& resp) {
        auto network = GetNetwork();
        if (network == nullptr) {
            return false;
        }
        auto http = network->CreateHttp(0);
        if (http == nullptr) {
            return false;
        }
        http->SetTimeout(6000);
        http->SetKeepAlive(false);
        http->SetHeader("Content-Type", "application/json");
        http->SetHeader("X-Device-Token", CONSOLE_DEVICE_TOKEN);
        http->SetContent(std::string(body));

        std::string base = ConsoleBase();
        std::string url = base + path;
        if (auto opened = http->Open("POST", url); !opened) {
            ESP_LOGW(TAG, "console %s 不可达: %s", url.c_str(), opened.error().ToString().c_str());
            http->Close();
            s_console_host_index = (s_console_host_index + 1) % kConsoleHostCount;
            return false;
        }
        auto status = http->GetStatusCode();
        resp = http->ReadAll();
        http->Close();
        if (!status) {
            s_console_host_index = (s_console_host_index + 1) % kConsoleHostCount;
            return false;
        }
        int code = *status;
        if (code < 200 || code >= 300) {
            ESP_LOGW(TAG, "console %s -> HTTP %d", url.c_str(), code);
            return false;
        }
        ESP_LOGI(TAG, "console ok: %s", kConsoleHosts[s_console_host_index]);
        return true;
    }

    // 心跳：只负责刷新「最后在线」。
    // 注册 / 激活码 / 固件升级都由 OTA 接口（POST /ota/）完成，这里不再重复。
    
void ReportHeartbeat() {
        std::string body = "{\"mac\":\"" + SystemInfo::GetMacAddress() +
                           "\",\"firmware\":\"" CONSOLE_FIRMWARE_VER "\"}";
        std::string resp;
        if (!ConsolePost("/api/devices/heartbeat", body, resp)) {
            return;
        }
        ESP_LOGD(TAG, "heartbeat ok");

        // 解析控制台下发的唤醒词，运行时重建命令表
        cJSON* root = cJSON_Parse(resp.c_str());
        if (root != nullptr) {
            cJSON* cfg = cJSON_GetObjectItem(root, "config");
            cJSON* ww = cfg ? cJSON_GetObjectItem(cfg, "wake_words") : nullptr;
            if (cJSON_IsArray(ww)) {
                std::vector<std::string> words;
                int n = cJSON_GetArraySize(ww);
                for (int i = 0; i < n; i++) {
                    cJSON* item = cJSON_GetArrayItem(ww, i);
                    cJSON* py = cJSON_GetObjectItem(item, "pinyin");
                    if (cJSON_IsString(py) && py->valuestring[0] != 0) {
                        words.push_back(py->valuestring);
                    }
                }
                auto saved = CustomWakeWord::LoadSavedWakeWords();
                if (!words.empty() && words != saved) {
                    if (CustomWakeWord::ReloadWakeWords(words)) {
                        ESP_LOGI(TAG, "唤醒词已按控制台配置更新（%d 个）", (int)words.size());
                    }
                }
            }

            // 控制台在线下发的动作，心跳时执行
            cJSON* cmds = cfg ? cJSON_GetObjectItem(cfg, "commands") : nullptr;
            if (cJSON_IsArray(cmds)) {
                int cn = cJSON_GetArraySize(cmds);
                for (int i = 0; i < cn; i++) {
                    cJSON* c = cJSON_GetArrayItem(cmds, i);
                    cJSON* k = cJSON_GetObjectItem(c, "kind");
                    cJSON* v = cJSON_GetObjectItem(c, "value");
                    if (!cJSON_IsString(k) || !cJSON_IsString(v)) {
                        continue;
                    }
                    std::string kind = k->valuestring;
                    std::string value = v->valuestring;
                    if (kind == "action") {
                        ExecuteAction(value);
                    } else if (kind == "volume") {
                        ApplyVolume(atoi(value.c_str()));
                    } else if (kind == "pose") {
                        // 自定义姿态：6 个角度用逗号分隔
                        int a[6] = {90, 90, 90, 90, 90, 90};
                        int n = 0;
                        size_t pos = 0;
                        while (n < 6 && pos <= value.size()) {
                            size_t comma = value.find(',', pos);
                            std::string part = value.substr(pos, comma == std::string::npos ? std::string::npos : comma - pos);
                            if (!part.empty()) {
                                a[n++] = atoi(part.c_str());
                            }
                            if (comma == std::string::npos) {
                                break;
                            }
                            pos = comma + 1;
                        }
                        ESP_LOGI(TAG, "自定义姿态: %d %d %d %d %d %d", a[0], a[1], a[2], a[3], a[4], a[5]);
                        servo_.MoveAll({a[0], a[1], a[2], a[3], a[4], a[5]}, 600);
                    } else if (kind == "led") {
                        // 灯效：value = "r,g,b" 或效果名
                        int r = 0, g = 0, b = 0;
                        if (sscanf(value.c_str(), "%d,%d,%d", &r, &g, &b) == 3) {
                            if (auto* _l = static_cast<DogLeds*>(GetLed())) {
                                _l->SetColor((uint8_t)r, (uint8_t)g, (uint8_t)b);
                            }
                            ESP_LOGI(TAG, "灯珠颜色: %d,%d,%d", r, g, b);
                        } else {
                            if (auto* _l = static_cast<DogLeds*>(GetLed())) {
                                _l->SetEffectByName(value);
                            }
                            ESP_LOGI(TAG, "灯效: %s", value.c_str());
                        }
                    } else if (kind == "connect") {
                        ESP_LOGI(TAG, "控制台请求唤醒：打开语音通道");
                        auto& _app = Application::GetInstance();
                        _app.Schedule([&_app]() {
                            if (_app.GetDeviceState() == kDeviceStateIdle) {
                                ESP_LOGI(TAG, "远程唤醒：开始聆听");
                                _app.StartListening();
                            } else {
                                ESP_LOGW(TAG, "非空闲状态，跳过远程唤醒");
                            }
                        });
                    }
                }
                ESP_LOGI(TAG, "执行控制台动作 %d 个", cn);
            }
            cJSON_Delete(root);
        }
    }

    static void ConsoleTaskEntry(void* arg) {
        auto* self = static_cast<DogBoard*>(arg);
        vTaskDelay(pdMS_TO_TICKS(8000));   // 等 OTA 先跑完
        while (true) {
            self->ReportHeartbeat();
            vTaskDelay(pdMS_TO_TICKS(CONSOLE_HEARTBEAT_MS));
        }
    }

    void StartConsoleReporter() {
        xTaskCreate(&DogBoard::ConsoleTaskEntry, "console_report", 4096, this, 3, nullptr);
    }

    void InitializeDisplayI2c() {
        i2c_master_bus_config_t bus_config = {};
        bus_config.i2c_port = (i2c_port_t)0;
        bus_config.sda_io_num = DISPLAY_SDA_PIN;
        bus_config.scl_io_num = DISPLAY_SCL_PIN;
        bus_config.clk_source = I2C_CLK_SRC_DEFAULT;
        bus_config.glitch_ignore_cnt = 7;
        bus_config.intr_priority = 0;
        bus_config.trans_queue_depth = 0;
        bus_config.flags.enable_internal_pullup = 1;
        ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &display_i2c_bus_));
    }

    void InitializeOledDisplay() {
        esp_lcd_panel_io_i2c_config_t io_config = {};
        io_config.dev_addr = 0x3C;
        io_config.scl_speed_hz = 400 * 1000;
        io_config.control_phase_bytes = 1;
        io_config.dc_bit_offset = 6;
        io_config.lcd_cmd_bits = 8;
        io_config.lcd_param_bits = 8;
        io_config.on_color_trans_done = nullptr;
        io_config.user_ctx = nullptr;
        io_config.flags.dc_low_on_data = 0;
        io_config.flags.disable_control_phase = 0;

        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c(display_i2c_bus_, &io_config, &panel_io_));

        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = GPIO_NUM_NC;
        panel_config.bits_per_pixel = 1;

        esp_lcd_panel_ssd1306_config_t ssd1306_config = {};
        ssd1306_config.height = static_cast<uint8_t>(DISPLAY_HEIGHT);
        panel_config.vendor_config = &ssd1306_config;

#ifdef SH1106
        ESP_ERROR_CHECK(esp_lcd_new_panel_sh1106(panel_io_, &panel_config, &panel_));
#else
        ESP_ERROR_CHECK(esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_));
#endif

        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        if (esp_lcd_panel_init(panel_) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to initialize display");
            return;
        }
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_, false));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

        display_ = new DogDisplay(panel_io_, panel_, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                  DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);

        // 本地关键词指令：识别文本直接驱动舵机，不依赖大模型
        display_->SetCommandHook([this](const std::string& text) {
            HandleVoiceCommand(text);
        });

    }

    // 启动阶段先显示文字提示（连接中 / 注册中 / 初始化），
    // 设备进入待命或对话状态后，再切到表情界面。
    void StartFaceSwitchTask() {
        xTaskCreate([](void* arg) {
            auto* self = static_cast<DogBoard*>(arg);
            auto& app = Application::GetInstance();
            for (int i = 0; i < 900; ++i) {   // 最多等约 4.5 分钟
                if (self->display_ != nullptr) {
                    auto st = app.GetDeviceState();
                    if (st == kDeviceStateIdle || st == kDeviceStateConnecting ||
                        st == kDeviceStateListening || st == kDeviceStateSpeaking) {
                        self->display_->EnterFaceMode();
                        ESP_LOGI(TAG, "init done, switch to FACE (state=%d)", (int)st);
                        break;
                    }
                }
                vTaskDelay(pdMS_TO_TICKS(300));
            }
            vTaskDelete(nullptr);
        }, "face_boot", 3072, this, 3, nullptr);
    }

    void InitializeButtons() {
        // 单击：开始 / 停止对话；开机时进入配网
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });

        // 长按：切换「显示文字 / 只显示表情」
        boot_button_.OnLongPress([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            if (display_ == nullptr) {
                return;
            }
            bool visible = display_->ToggleTextVisible();
            ESP_LOGW(TAG, "display mode -> %s", visible ? "TEXT" : "FACE");
        });
    }


    // 本地关键词指令：不依赖大模型，识别到就动
    // 音量设置（0-100），持久化到 NVS，重启后保持
    void ApplyVolume(int vol) {
        if (vol < 0) vol = 0;
        if (vol > 100) vol = 100;
        auto codec = GetAudioCodec();
        if (codec != nullptr) {
            codec->SetOutputVolume(vol);
        }
        Settings settings("audio", true);
        settings.SetInt("volume", vol);
        ESP_LOGI(TAG, "音量设为 %d", vol);
    }
    // 控制台下发的动作编码（英文）
    void ExecuteAction(const std::string& a) {
        ESP_LOGI(TAG, "控制台动作: %s", a.c_str());
        if (a == "stand") { servo_.Stand(); }
        else if (a == "sit") { servo_.Sit(); }
        else if (a == "walk") { servo_.WalkForward(4); }
        else if (a == "back") { servo_.WalkBackward(4); }
        else if (a == "left") { servo_.TurnLeft(3); }
        else if (a == "right") { servo_.TurnRight(3); }
        else if (a == "dance") { servo_.Dance(4); }
        else if (a == "lie") { servo_.LieDown(); }
        else if (a == "sleep") { servo_.Sleep(); }
        else if (a == "wake") { servo_.WakeUp(); }
        else if (a == "wag") { servo_.Wag(3); }
        else if (a == "shake") { servo_.ShakeHead(2); }
        else { ESP_LOGW(TAG, "未知动作: %s", a.c_str()); }
    }

    void HandleVoiceCommand(const std::string& text) {
        struct Rule { const char* kw; int action; };
        // action: 0 stand 1 sit 2 walk 3 back 4 left 5 right 6 dance 7 lie 8 sleep 9 wake 10 wag 11 shake 12 stop
        static const Rule kRules[] = {
            {"往前走", 2}, {"向前走", 2}, {"前进", 2},
            {"往后退", 3}, {"后退", 3},
            {"左转", 4}, {"往左转", 4},
            {"右转", 5}, {"往右转", 5},
            {"跳舞", 6}, {"跳个舞", 6},
            {"趴下", 7}, {"趴着", 7},
            {"睡觉", 8}, {"休息一下", 8},
            {"起身", 9}, {"起来", 9}, {"站起来", 0},
            {"坐下", 1}, {"坐一下", 1},
            {"摇尾巴", 10}, {"摇摇头", 11}, {"停下", 12}, {"停", 12},
        };
        for (const auto& r : kRules) {
            if (text.find(r.kw) == std::string::npos) {
                continue;
            }
            ESP_LOGI(TAG, "本地指令命中: %s", r.kw);
            switch (r.action) {
                case 0: servo_.Stand(); break;
                case 1: servo_.Sit(); break;
                case 2: servo_.WalkForward(4); break;
                case 3: servo_.WalkBackward(4); break;
                case 4: servo_.TurnLeft(3); break;
                case 5: servo_.TurnRight(3); break;
                case 6: servo_.Dance(2); break;
                case 7: servo_.LieDown(); break;
                case 8: servo_.Sleep(); break;
                case 9: servo_.WakeUp(); break;
                case 10: servo_.Wag(3); break;
                case 11: servo_.ShakeHead(2); break;
                case 12: servo_.Stand(); break;
                default: break;
            }
            return;
        }
    }

    // —— 语音可控的动作 / 表情，通过 MCP 工具暴露给大模型 ——
    void InitializeTools() {
        auto& mcp_server = McpServer::GetInstance();

        mcp_server.AddTool(
            "self.face_expression",
            "让机器狗做出指定表情并在几秒后恢复。expression 可选："
            "happy(开心)、angry(生气)、sad(难过)、surprised(惊讶)、sleepy(睡觉)、"
            "love(喜欢)、wink(眨眼)、neutral(平常)。"
            "用户说「做一个生气的表情」时调用本工具，参数 expression=angry。",
            PropertyList({Property("expression", kPropertyTypeString)}),
            [this](const PropertyList& properties) -> ToolResult {
                auto expr = properties["expression"].value<std::string>();
                ESP_LOGI(TAG, "face_expression: %s", expr.c_str());
                if (display_ == nullptr) {
                    return false;
                }
                display_->ShowTemporaryExpression(expr.c_str(), 4000);
                return true;
            });

        mcp_server.AddTool(
            "self.dog_action",
            "控制机器狗做动作。action 可选：stand(站立)、sit(坐下)、walk(前进)、wag(摇尾巴)、"
            "shake(摇头)、stop(停下)。",
            PropertyList({Property("action", kPropertyTypeString)}),
            [this](const PropertyList& properties) -> ToolResult {
                auto action = properties["action"].value<std::string>();
                ESP_LOGI(TAG, "dog_action: %s", action.c_str());
                if (action == "stand") {
                    servo_.Stand();
                } else if (action == "sit") {
                    servo_.Sit();
                } else if (action == "walk") {
                    servo_.WalkForward(4);
                } else if (action == "wag") {
                    servo_.Wag(3);
                } else if (action == "shake") {
                    servo_.ShakeHead(2);
                } else if (action == "stop") {
                    servo_.Stand();
                } else {
                    return false;
                }
                return true;
            });

        // 动作序列用：一次设置 4~6 路角度（"90,50,90,121" 或带 6 位）
        mcp_server.AddTool(
            "self.set_pose",
            "一次设置多路舵机角度，用于动作序列。angles 为逗号分隔的角度，"
            "例如 \"90,50,90,121\"（左前,左后,右前,右后）或 6 个值含竖直/头部。",
            PropertyList({
                Property("angles", kPropertyTypeString),
            }),
            [this](const PropertyList& properties) -> ToolResult {
                std::string s = properties["angles"].value<std::string>();
                int a[6] = {90, 90, 90, 90, 90, 90};
                int n = 0;
                size_t pos = 0;
                while (n < 6 && pos <= s.size()) {
                    size_t comma = s.find(',', pos);
                    std::string part = s.substr(pos, comma == std::string::npos ? std::string::npos : comma - pos);
                    if (!part.empty()) {
                        a[n++] = atoi(part.c_str());
                    }
                    if (comma == std::string::npos) {
                        break;
                    }
                    pos = comma + 1;
                }
                for (int i = 0; i < n; i++) {
                    servo_.SetAngle(static_cast<ServoId>(i), a[i]);
                }
                ESP_LOGI(TAG, "set_pose: %d 路", n);
                return true;
            });

        mcp_server.AddTool(
            "self.set_servo",
            "直接设置某一路舵机角度。servo 取值 0-5（0左前 1左后 2右前 3右后 4竖直 5头部），angle 为 0-180 度。",
            PropertyList({
                Property("servo", kPropertyTypeInteger, 0, 5),
                Property("angle", kPropertyTypeInteger, 0, 180),
            }),
            [this](const PropertyList& properties) -> ToolResult {
                int idx = properties["servo"].value<int>();
                int angle = properties["angle"].value<int>();
                servo_.MoveTo(static_cast<ServoId>(idx), angle, 300);
                return true;
            });

        // 校准用：单条腿相对点动
        mcp_server.AddTool(
            "self.leg_move",
            "调试用：让某一条腿相对转动。leg 取值 0-3（0左前 1左后 2右前 3右后），"
            "delta 为角度增量，正数负数都行，例如 15 或 -15。",
            PropertyList({
                Property("leg", kPropertyTypeInteger, 0, 3),
                Property("delta", kPropertyTypeInteger, -60, 60),
            }),
            [this](const PropertyList& properties) -> ToolResult {
                int leg = properties["leg"].value<int>();
                int delta = properties["delta"].value<int>();
                servo_.Nudge(static_cast<ServoId>(leg), delta);
                return true;
            });

        // 校准用：四条腿依次点动，用来确认编号和方向
        mcp_server.AddTool(
            "self.leg_test",
            "调试用：四条腿依次点动一下（左前、左后、右前、右后），用来确认哪条腿对应哪个编号、方向是否正确。",
            PropertyList(),
            [this](const PropertyList& properties) -> ToolResult {
                servo_.LegTest();
                return true;
            });

        // 表情：显示在 OLED 的表情区（Noto Emoji 字形）
        mcp_server.AddTool(
            "self.set_emotion",
            "让机器狗在屏幕上显示一个表情。emotion 可选：neutral、happy、laughing、sad、angry、"
            "surprised、sleepy、thinking、cool、love、confused。",
            PropertyList({Property("emotion", kPropertyTypeString)}),
            [this](const PropertyList& properties) -> ToolResult {
                auto emotion = properties["emotion"].value<std::string>();
                if (display_ == nullptr) {
                    return false;
                }
                display_->SetEmotion(emotion.c_str());
                return true;
            });

#if DOG_USE_WS2812
        // 颜色：red/green/blue/white/yellow/cyan/purple/pink/orange/warm/off 或 #RRGGBB
        mcp_server.AddTool(
            "self.set_led",
            "设置机器狗身上 WS2812 灯的颜色。color 可以是 red、green、blue、white、yellow、"
            "cyan、purple、pink、orange、warm、off，也可以直接给 #RRGGBB。",
            PropertyList({Property("color", kPropertyTypeString)}),
            [this](const PropertyList& properties) -> ToolResult {
                auto* leds = static_cast<DogLeds*>(GetLed());
                if (leds == nullptr) {
                    return false;
                }
                auto name = properties["color"].value<std::string>();
                uint8_t r = 0, g = 0, b = 0;
                if (!leds->ParseColor(name, r, g, b)) {
                    ESP_LOGW(TAG, "unknown color: %s", name.c_str());
                    return false;
                }
                ESP_LOGI(TAG, "led color %s -> (%d,%d,%d)", name.c_str(), r, g, b);
                leds->SetColor(r, g, b);
                return true;
            });

        // 灯效：rainbow / breathing / blink / chase / auto / off
        mcp_server.AddTool(
            "self.led_effect",
            "给机器狗放灯效。effect 可选：rainbow（彩虹）、breathing（呼吸）、blink（闪烁）、"
            "chase（流水）、auto（跟随状态）、off（关灯）。",
            PropertyList({Property("effect", kPropertyTypeString)}),
            [this](const PropertyList& properties) -> ToolResult {
                auto* leds = static_cast<DogLeds*>(GetLed());
                if (leds == nullptr) {
                    return false;
                }
                auto name = properties["effect"].value<std::string>();
                ESP_LOGI(TAG, "led effect: %s", name.c_str());
                leds->SetEffectByName(name);
                return leds->effect() != DogLeds::Effect::kAuto;
            });
#endif
    }

public:
    DogBoard() : boot_button_(BOOT_BUTTON_GPIO, false, 800, 50) {
        InitializeDisplayI2c();
        InitializeOledDisplay();
        InitializeButtons();
        servo_.Initialize();
        servo_.Stand();
        InitializeTools();
        StartConsoleReporter();   // 注册到控制台，拿激活码
        StartFaceSwitchTask();   // 初始化完成后再切表情界面
    }

    virtual AudioCodec* GetAudioCodec() override {
#ifdef AUDIO_I2S_METHOD_SIMPLEX
        static NoAudioCodecSimplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK, AUDIO_I2S_SPK_GPIO_LRCK, AUDIO_I2S_SPK_GPIO_DOUT,
            AUDIO_I2S_MIC_GPIO_SCK, AUDIO_I2S_MIC_GPIO_WS, AUDIO_I2S_MIC_GPIO_DIN);
#else
        static NoAudioCodecDuplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_GPIO_BCLK, AUDIO_I2S_GPIO_WS, AUDIO_I2S_GPIO_DOUT, AUDIO_I2S_GPIO_DIN);
#endif
        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }

#if DOG_USE_WS2812
    virtual Led* GetLed() override {
        static DogLeds leds(WS2812_GPIO, WS2812_COUNT, WS2812_GPIO_2, WS2812_COUNT_2);
        return &leds;
    }
#endif

};

DECLARE_BOARD(DogBoard);

