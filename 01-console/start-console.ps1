# 一键启动：知识库/记忆服务(8077) + 控制台(80)
#
# 用法：
#   1. 把 .env.example 复制为 .env，填好密码、令牌和服务地址
#   2. 以普通权限运行本脚本
#
# 依赖：console/.venv 与 kb-service/.venv 已按 requirements.txt 安装好

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$kb = Join-Path (Split-Path -Parent $root) "kb-service"
$ui = $root

# ---- 读取 .env ----
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ".env 不存在，请先复制 .env.example 并填写。" -ForegroundColor Red
    exit 1
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $idx = $line.IndexOf("=")
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1).Trim()
        if ($v) { Set-Item -Path "env:$k" -Value $v }
    }
}

if (-not $env:DEVICE_TOKEN) {
    Write-Host "警告：.env 里没有 DEVICE_TOKEN，设备接入会被拒绝（503）。" -ForegroundColor Yellow
}

# ---- 清理旧进程 ----
foreach ($p in 8077, 80) {
    $c = netstat -ano | Select-String ":$p\s+.*LISTENING"
    if ($c) {
        Write-Host "端口 $p 被占用，清理旧进程..." -ForegroundColor Yellow
        $c | ForEach-Object {
            $procId = ($_ -split '\s+')[-1]
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
}

# ---- 知识库服务 ----
$env:KB_VECTOR_BACKEND = "local"
$env:KB_EMBED_BACKEND = "hash"
$env:KB_DATA_DIR = "./data"
$env:KB_SQLITE = "./data/memory.db"

Start-Process -FilePath (Join-Path $kb ".venv\Scripts\python.exe") `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8077" `
    -WorkingDirectory $kb -WindowStyle Minimized

Start-Sleep -Seconds 2

# ---- 控制台 ----
Start-Process -FilePath (Join-Path $ui ".venv\Scripts\python.exe") `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80" `
    -WorkingDirectory $ui -WindowStyle Minimized

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "  控制台      http://127.0.0.1" -ForegroundColor Green
Write-Host "  知识库 API  http://127.0.0.1:8077/docs" -ForegroundColor Green
Write-Host "  模型服务    $env:LLM_CHAT_URL" -ForegroundColor Green
Write-Host "  语音服务    $env:WS_URL" -ForegroundColor Green
Write-Host ""
