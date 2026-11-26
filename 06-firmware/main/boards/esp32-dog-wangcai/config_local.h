#pragma once
// 本机私有配置 —— 不要提交到仓库（已在 .gitignore 中）
// 覆盖 dog_board.cc 里的默认占位值

// 控制台地址候选（设备连不上第一个会自动试第二个）
// 注意：不能用 100.x.x.x（Tailscale 网段），ESP32 没有该路由
#define CONSOLE_HOST_1 "http://<你的服务器局域网IP>"   // 手机热点
#define CONSOLE_HOST_2 "http://10.93.19.230"      // 校园 / 公司 WiFi

// 设备令牌，必须与控制台环境变量 DEVICE_TOKEN 一致
#define CONSOLE_DEVICE_TOKEN "<REDACTED>"
