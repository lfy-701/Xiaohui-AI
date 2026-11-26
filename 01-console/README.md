# console · 小慧控制台

设备管理、语音调试、知识库与记忆查看、固件发布、MCP 工具的统一控制台。

## 结构

```text
console/
├── app/
│   ├── main.py     HTTP 接口、设备 OTA、语音与 MCP 代理
│   ├── db.py       SQLite 存储（设备 / 日志 / 会话 / 固件）
│   ├── auth.py     登录与 Cookie 会话
│   └── llm.py      模型服务的 OpenAI 兼容调用
├── static/
│   └── index.html  单页控制台（无需构建）
├── .env.example    配置模板
├── requirements.txt
└── start-console.ps1
```

## 启动

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env    # 然后按需修改
.\start-console.ps1
```

访问 <http://127.0.0.1>。

## 环境变量

| 变量 | 说明 | 是否必需 |
|---|---|---|
| `CONSOLE_PASSWORD` | 登录密码，留空则不启用登录 | 建议 |
| `DEVICE_TOKEN` | 设备接入令牌，需与固件一致 | **设备接入必需** |
| `KB_URL` | 知识库服务地址 | 用知识库时必需 |
| `LLM_CHAT_URL` | 模型服务（OpenAI 兼容） | 用「试聊」时必需 |
| `MCP_BASE_URL` | 模型服务的 MCP 管理接口 | 用 MCP 页签时必需 |
| `MCP_ADMIN_TOKEN` | MCP 远程写令牌，仅后端使用 | 可选 |
| `WS_URL` | 语音服务 WebSocket 地址，OTA 下发给设备 | **语音对话必需** |
| `MUSIC_BASE_URL` | 音乐 MCP 服务地址 | 用音乐页签时必需 |

`DEVICE_TOKEN` 为空时，设备注册与心跳接口返回 503，不做「空令牌放行」处理。

## 设备接入流程

1. 设备开机后请求 `POST /ota/`
2. 未绑定：返回激活码，设备屏幕显示
3. 在控制台设备页输入激活码完成绑定
4. 已绑定：返回 `websocket.url`，设备据此连接语音服务

> 已绑定时接口**不再返回 `activation` 字段**。固件只要看到该字段就会进入激活重试循环，无法继续连接语音服务。

## 自测

```powershell
python -c "import app.main"
git diff --check
```
