# Pull Request：配置页、语音设置、表情界面与运行时唤醒词

## 基本信息

| 项目 | 值 |
|---|---|
| Base | `main`（如 `feature/memory-kb` 尚未合并，建议 Base 先选 `feature/memory-kb`） |
| Compare | `feature/member-b-console-firmware` |
| 提交 | `d5d9edd` |
| 改动规模 | 8 文件 / +1514 −59（相对 `feature/memory-kb`）|

## 一、修改目的

本轮把「配置」做成可用的一体化后台，并补齐设备端的表情与唤醒词能力：

1. **配置页改版**：原来的长表单改成三个标签页（角色 / 模型与记忆 / 语音设置），角色介绍改为结构化模板 + 自定义弹层。
2. **配置实时下发**：保存后音色、角色设定、模型、唤醒词都能作用到设备，不需要重启服务或重新配网。
3. **设备表情界面**：开机显示文字提示，初始化完成后自动切到狗脸；长按 BOOT 键切回文字。共 11 种表情。
4. **唤醒词可改**：控制台改唤醒词 → 心跳下发 → 设备运行时重建 MultiNet 命令表 → 写入 NVS。

## 二、影响目录

```
console/app/main.py                     配置同步、拼音转换、OTA 动态地址
console/static/index.html               标签式配置页、表情预览、保存栏
console/requirements.txt                新增 pypinyin
firmware/boards/esp32-dog-wangcai/
  ├── dog_face.h / dog_face.cc          新增：表情渲染（11 种）
  ├── dog_display.h                      双模式显示（表情 / 文字）
  └── dog_board.cc                       启动时序、表情工具、唤醒词下发
firmware/patches/README.md              补充第 5~8 节改动说明
```

**未改动**：`kb-service/`、`services/music-mcp/`、`model-service/`、`knowledge_base/`。

## 三、共享接口变化

| 接口 | 变化 | 兼容性 |
|---|---|---|
| `POST /api/devices/heartbeat` | 响应新增 `config.wake_words: [{pinyin, display}]` | **向后兼容**：旧固件忽略该字段 |
| `POST /ota/` | `websocket.url` 改为按设备实际访问到的地址生成 | **行为变化**：不再使用固定 `WS_URL` 的主机部分 |
| `PUT /api/agents/{id}` | 保存时同步写入语音服务运行时配置 | 无接口签名变化 |
| 设备 MCP 工具 | 新增 `self.face_expression` | 新增工具，不影响已有工具 |

**需要成员 A 确认的一点**：`/ota/` 的 websocket 地址现在从请求的 `Host` 头推导主机，
端口与路径仍取自 `WS_URL`。这样电脑换网络（热点 / 校园网）后不用改配置。
如果模型服务依赖固定域名，请告知，我改成「优先配置、回退推导」。

## 四、测试命令与真实结果

**控制台**

```powershell
python -c "import ast; ast.parse(open('console/app/main.py', encoding='utf-8').read())"
```

结果：通过（已顺带移除文件头 BOM）。

**配置同步（运行时）**

```
保存 agent → 读取 /api/voice/settings
  prompt 首行 : # Role: 小慧 · 元气开心果
  prompt 长度 : 255
  voice       : zh-CN-YunxiNeural
  model       : qwen2.5:3b
  wake_words  : ['你好小慧']
```

**唤醒词下发**

```
改唤醒词为「小慧小慧」→ 心跳响应：
[{'pinyin': 'ni hao xiao hui', 'display': '你好小慧'},
 {'pinyin': 'xiao hui xiao hui', 'display': '小慧小慧'}]
```

**固件构建**

```
idf.py build → xiaozhi.bin 2.48 MB，剩余 37%
```

**表情渲染预览**：见 `docs/face_preview.png`（11 种表情的等尺寸模拟图）。

## 五、未完成的测试与原因

| 项目 | 原因 |
|---|---|
| 表情在真机上的观感 | 需要实际 OLED 观察，代码已按 128×64 坐标逐像素规划 |
| 运行时唤醒词重建的实际识别率 | 需要真机说话验证；`esp_mn_commands_update()` 已调用，失败会回退到 NVS 旧词表 |
| 换网后 OTA 推导地址 | 需要两台不同网段的设备验证 |

## 六、配置要求

| 项 | 说明 |
|---|---|
| `pypinyin` | 控制台新增依赖，已写入 requirements.txt |
| `DEVICE_TOKEN` | 仍是环境变量，仓库内只有占位符 |
| `WS_URL` | 现在只用它的端口和路径，主机由请求推导 |
| 固件 `CONSOLE_DEVICE_TOKEN` | 需与控制台一致，源码内为 `CHANGE_ME_DEVICE_TOKEN` |

## 七、已知限制

1. 唤醒词靠心跳下发，最迟 30 秒生效；设备离线时不会更新。
2. 唤醒词是拼音匹配，用户需输入中文（控制台自动转拼音）；输入拼音会被当成英文处理。
3. 两字唤醒词（如「小慧」）识别率低于四字，建议用「你好小慧」或「小慧小慧」。
4. 表情的 `Zz` 依赖内置文本字体的 ASCII 字形，若字体缺失会显示为方框。
5. 运行时重建命令表期间，正在进行的唤醒检测会短暂中断。

## 八、回滚方式

```powershell
git revert --no-commit d5d9edd
git commit -m "revert: 撤回配置页与表情改动"
```

固件侧回滚：重新刷入 `feature/memory-kb` 对应版本的 `xiaozhi.bin`。

## 九、PR 创建入口

<https://github.com/hdaefadhj/xiaoxiao-ai/pull/new/feature/member-b-console-firmware>
