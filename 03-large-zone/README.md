# 小慧大模型专区 · 独立部署包

一个**独立进程、独立端口（8013）、独立配置**的大模型控制台，部署在小慧控制台主机上，
与现有小模型完全隔离。

- 现有小慧控制台：`http://100.100.221.34/`（不动）
- 小模型服务：8000 / 8009 / 810x（不动）
- 大模型专区：`http://100.100.221.34:8013/`（本包）

## 1. 隔离边界

| 项目 | 本专区 | 现有小慧控制台 |
| --- | --- | --- |
| 目录 | 自己的安装目录（如 `D:\xiaohui-large-zone`） | 原目录 |
| Python 环境 | 自己的 `.venv` | 原环境 |
| 端口 | 8013 | 80 / 8080 |
| 数据库 | 无（服务端无状态） | `console.db` |
| 配置 | 自己的 `.env` | 原配置 |
| 模型 | DeepSeek 云端 API | Ollama 小模型 |

本专区**不会读取或修改 `console.db`**，也不会调用 8000/8009/810x。
两个控制台可以同时运行、互不影响；停掉本专区不影响小慧。

---

## 2. Windows 安装（推荐）

前提：控制台主机已安装 **Python 3.11**（`py -3.11 --version` 能输出）。

1. 把整个 `xiaohui-large-zone` 目录解压到例如 `D:\xiaohui-large-zone`。
2. 在目录里打开 PowerShell，执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

3. 安装脚本会：
   - 创建独立 `.venv`
   - 安装依赖
   - 从 `.env.example` 生成 `.env`
   - 自动生成一个 32 位控制台令牌并打印出来
4. 编辑 `.env`，只改这一行：

```ini
DEEPSEEK_API_KEY=""
```

5. 启动：

```powershell
# 前台调试（Ctrl+C 停止）
.\start-windows.ps1

# 或后台运行
.\start-background.ps1
```

6. 打开 `http://127.0.0.1:8013/`，输入安装时打印的令牌。

> 令牌也可以自己改 `.env` 里的 `CONSOLE_TOKEN`（至少 16 位），改完重启。

### 让其他机器访问

管理员 PowerShell 执行一次：

```powershell
New-NetFirewallRule -DisplayName "Xiaohui Large Zone 8013" -Direction Inbound -Protocol TCP -LocalPort 8013 -Action Allow
```

然后用 `http://100.100.221.34:8013/` 访问。

### 开机自启（可选）

```powershell
schtasks /Create /TN "XiaohuiLargeZone" ^
  /TR "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File D:\xiaohui-large-zone\start-background.ps1" ^
  /SC ONSTART /RU SYSTEM
```

路径按实际安装目录改；需要管理员权限。

---

## 3. Linux 安装（可选）

```bash
tar xzf xiaohui-large-zone.tar.gz
cd xiaohui-large-zone
bash install-linux.sh
# 编辑 .env 填 DEEPSEEK_API_KEY
.venv/bin/python run_zone.py          # 前台
sudo bash install-service-linux.sh    # systemd 常驻
```

日志：`journalctl -u xiaohui-large -f`

---

## 4. 自检

```powershell
# Windows
.\.venv\Scripts\python.exe verify-zone.py

# 额外发一句真实对话（消耗额度）
.\.venv\Scripts\python.exe verify-zone.py --chat
```

期望：

- `/health` 200，`configured=true`
- `/api/v1/console/overview` 200
- 对话 200，返回一句中文回复

---

## 5. 在日常控制台加入口（可选）

本包**不修改**现有控制台的任何文件。如果想让成员从现有控制台点进来，只需在现有
控制台的导航/首页加一个普通链接：

```html
<a href="http://100.100.221.34:8013/" target="_blank" rel="noreferrer">大模型专区</a>
```

这只是一行链接，不涉及数据库、不涉及模型服务，也不共享登录态。

---

## 6. 升级与回滚

**升级**：

1. `.\stop-windows.ps1`
2. 备份 `.env`
3. 用新包覆盖 `app/`、`run_zone.py`、`requirements.txt`
4. `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
5. `.\start-background.ps1`

**回滚**：`.\stop-windows.ps1`，删除本目录即可。现有小慧控制台、`console.db`、
8000/8009 均未被修改。

---

## 7. 安全说明（务必看）

- 8013 **只应在 Tailscale / 可信局域网内**使用，不要直接映射到公网。
- 控制台概览接口有 `CONSOLE_TOKEN` 保护，页面会弹窗输入。
- `/api/v1/chat` 目前**没有设备鉴权**：能访问 8013 的人都可以调用并消耗 DeepSeek 额度。
  这是阶段 5 要补的 `DEVICE_TOKEN`；在此之前请依赖 Tailscale ACL。
- DeepSeek 密钥只写在 `.env`，不要写进固件、聊天记录或截图。
- `.env` 不要提交到 Git、不要打进压缩包再分发。

---

## 8. 故障排查

| 现象 | 处理 |
| --- | --- |
| `py -3.11` 找不到 | 安装 Python 3.11，勾选 Add to PATH |
| pip 很慢/超时 | 用 `-IndexUrl https://pypi.tuna.tsinghua.edu.cn/simple` 重跑安装 |
| 8013 被占用 | 改 `.env` 的 `APP_PORT`，并同步防火墙规则 |
| 页面提示“需要令牌” | 输入 `.env` 里的 `CONSOLE_TOKEN` |
| `/health` 显示 `configured=false` | `.env` 里的 `DEEPSEEK_API_KEY` 没填或为空 |
| 对话 502 `upstream_auth_failed` | 密钥错误/失效 |
| 其他机器打不开 | 防火墙未放行 8013，或绑定地址不是 `0.0.0.0` |
| 启动报 `WinError 10013` | 端口被占用，换端口 |
