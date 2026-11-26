# 小慧 AI 机器狗

一只会说话、会做动作的 AI 桌宠：ESP32-S3 硬件 + 自建语音服务 + 管理控制台。

## 目录结构

| 目录 | 说明 |
|---|---|
| `01-console/` | 控制台（FastAPI + 单页前端，端口 8080）：设备管理、动作面板、语音设置、OTA 下发 |
| `02-voice-server/` | 语音服务（端口 8000 WS / 8003 HTTP）：VAD → ASR → LLM → TTS 全链路编排 |
| `03-large-zone/` | 大模型专区（端口 8013）：DeepSeek API 封装、工具循环、SSE 流式、天气速答 |
| `04-kb-service/` | 知识库服务（端口 8077） |
| `05-music-mcp/` | 音乐 MCP 服务（端口 8102） |
| `06-firmware/` | ESP32 固件（xiaozhi-esp32 定制） |
| `07-tools/` | 运维脚本：一键启动、内存守卫、串口采集、页码迁移 |
| `08-docs/` | 设计文档、交接文档、实施报告 |

## 架构

```
设备（ESP32-S3）──WS/opus──> 语音服务 8000
                                ├─ VAD（Silero）
                                ├─ ASR（FunASR SenseVoice，本地）
                                ├─ 路由 → 大模型专区 8013 ──> DeepSeek API
                                └─ TTS（Edge / 可换本地）
控制台 8080 ──HTTP──> 语音服务 8003（状态/播报/动作）
           └──OTA──> 设备（下发 websocket 地址与配置）
```

## 快速开始

```powershell
# 1) 各子项目装依赖（各自 venv）
cd 02-voice-server; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt

# 2) 配置密钥（复制 .env.example 后填写）
copy .env.example .env

# 3) 一键启动
powershell -ExecutionPolicy Bypass -File 07-tools\xiaohui_start_all.ps1
```

## 关键配置

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `ZONE_MODE` | `all` 全部走专区 / `hybrid` 只难题走专区 | `all` |
| `ZONE_ALL_CLOUD` | `1` 全部走云端大模型，不走本地小模型 | `1` |
| `ZONE_STREAM` | `1` 专区 SSE 流式，首句优先 | `1` |
| `TTS_CONCURRENCY` | 多句并发预合成路数，`1` 为串行 | `2` |
| `TTS_TIMEOUT_S` | TTS 单句硬超时 | `12` |

## 性能（真机实测）

| 指标 | 数值 |
|---|---|
| LLM 首字（DeepSeek 流式） | 0.68~1.10 s |
| TTS 首块（Edge） | 1.9~2.2 s |
| 起播（服务端到首帧） | 2.8~3.3 s |
| 缓存命中句 | 0.00 s |

## 说明

- 本仓库**不含任何密钥**：所有 `api_key` / `token` / `secret` 已清空，`.env` 已加入 `.gitignore`。
- 大模型权重、音频缓存、固件二进制产物未入库，需按 `02-voice-server/models/模型下载说明.md` 自行下载。
- 硬件为 ESP32-S3 + INMP441 麦克风 + MAX98357 功放 + 舵机腿。
