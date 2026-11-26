"""固件：新增 self.set_pose 工具（一次设置多路舵机角度，供动作序列逐帧调用）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

F = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai\dog_board.cc")
t = F.read_text(encoding="utf-8")

if "self.set_pose" in t:
    print("已存在 set_pose")
    raise SystemExit(0)

ANCHOR = '''        mcp_server.AddTool(
            "self.set_servo",'''

NEW = '''        // 动作序列用：一次设置 4~6 路角度（"90,50,90,121" 或带 6 位）
        mcp_server.AddTool(
            "self.set_pose",
            "一次设置多路舵机角度，用于动作序列。angles 为逗号分隔的角度，"
            "例如 \\"90,50,90,121\\"（左前,左后,右前,右后）或 6 个值含竖直/头部。",
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
            "self.set_servo",'''

if ANCHOR in t:
    t = t.replace(ANCHOR, NEW, 1)
    F.write_text(t, encoding="utf-8")
    print("固件：已加 self.set_pose")
else:
    print("未找到锚点")
