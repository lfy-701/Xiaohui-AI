# 启动控制台（带齐必需环境变量 + 日志落盘），已存在监听则跳过
param([switch]$Force)

$Root = "D:\AI-Companion-shared\xiaohui-ai"
$Console = "$Root\console"
$LogDir = "D:\AI-Companion-shared\xiaohui-ai\logs"
$Log = Join-Path $LogDir "console.log"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Port-Listening([int]$port) {
    $m = netstat -ano | Select-String ":$port\s.*LISTENING"
    return [bool]$m
}

if (-not $Force -and (Port-Listening 8080)) { "console 已在运行 (8080)"; exit 0 }

$env:KB_URL            = "http://127.0.0.1:8077"
$env:LLM_CHAT_URL      = "http://<本地模型服务器IP>:8000/v1/chat/completions"
$env:WS_URL            = "ws://<你的服务器局域网IP>:8000/xiaozhi/v1/"
$env:MCP_BASE_URL      = "http://<本地模型服务器IP>:8000"
$env:MUSIC_BASE_URL    = "http://127.0.0.1:8102"
$env:VOICE_HTTP_BASE   = "http://127.0.0.1:8003"
$env:VOICE_DIR         = "C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server"
$env:AUDIO_CACHE_BASE  = "http://<你的服务器局域网IP>:8080/audio"
$env:AUDIO_UPSTREAM    = "http://<本地模型服务器IP>:8106"
$env:LLM_MAX_TOKENS    = "120"
$env:LLM_WARMUP_SECONDS= "240"
$env:HARDWARE_TOKEN    = "<REDACTED>"
$env:DEVICE_TOKEN      = "<REDACTED>"
$env:LLM_PROVIDER      = "openai"
$env:ZONE_URL          = "http://127.0.0.1:8013"
$env:ZONE_MODE         = "all"
$env:XIAOHUI_DEFAULT_CITY = "东莞"

$py = "$Console\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "console venv python 不存在: $py" }

Start-Process -FilePath $py `
    -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8080" `
    -WorkingDirectory $Console -WindowStyle Hidden `
    -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"

for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    if (Port-Listening 8080) { "console 已启动 (8080)，日志: $Log"; exit 0 }
}
"console 未能在 40 秒内监听 8080，检查 $Log 和 $Log.err"
exit 1
