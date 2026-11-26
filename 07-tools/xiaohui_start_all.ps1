# 小慧全服务一键启动（开机自启调用）
$ErrorActionPreference = "SilentlyContinue"
$LogDir = "D:\AI-Companion-shared\xiaohui-ai\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$Log = Join-Path $LogDir ("startup-" + (Get-Date -Format "yyyyMMdd") + ".log")

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Write-Host $line
}
function Test-Port([int]$port) {
    # 不用 Get-NetTCPConnection：在某些受限/沙箱上下文里它会静默返回空，
    # 导致脚本误判端口空闲并重复拉起服务。netstat 到处都能用。
    $m = netstat -ano | Select-String ":$port\s.*LISTENING"
    return [bool]$m
}
function Start-Svc([string]$name, [int]$port, [string]$exe, [string]$argLine, [string]$workdir, [hashtable]$env) {
    if (Test-Port $port) { Write-Log "[skip] $name ($port)"; return }
    foreach ($k in $env.Keys) { Set-Item -Path "env:$k" -Value $env[$k] }
    Start-Process -FilePath $exe -ArgumentList $argLine -WorkingDirectory $workdir -WindowStyle Hidden
    Start-Sleep -Seconds 1
    Write-Log "[start] $name ($port)"
}
function Test-Watchdog([string]$pattern) {
    $p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$pattern*" }
    return [bool]$p
}

$Root = "D:\AI-Companion-shared\xiaohui-ai"
$Py        = "D:\Anaconda3\python.exe"                          # 音乐服务用（无第三方依赖）
$ConsolePy = "$Root\console\.venv\Scripts\python.exe"           # 控制台必须用自身 venv（Anaconda 没装 uvicorn）
$KbPy      = "$Root\kb-service\.venv\Scripts\python.exe"        # 知识库同理
$Voice = "C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server"
$Zone = "D:\xiaohui-large-zone"
$Tools = "C:\Users\53487\Documents\deepseek-harness\default-workspace\tools"

Write-Log "===== 小慧服务启动 ====="

Start-Svc "知识库" 8077 $KbPy "-m uvicorn app.main:app --host 127.0.0.1 --port 8077" "$Root\kb-service" @{}
Start-Svc "音乐服务" 8102 $Py "server.py" "$Root\services\music-mcp" @{}
Start-Svc "控制台" 8080 $ConsolePy "-m uvicorn app.main:app --host 0.0.0.0 --port 8080" "$Root\console" @{
    KB_URL = "http://127.0.0.1:8077"
    LLM_CHAT_URL = "http://<本地模型服务器IP>:8000/v1/chat/completions"
    WS_URL = "ws://<你的服务器局域网IP>:8000/xiaozhi/v1/"
    MCP_BASE_URL = "http://<本地模型服务器IP>:8000"
    MUSIC_BASE_URL = "http://127.0.0.1:8102"
    VOICE_HTTP_BASE = "http://127.0.0.1:8003"
    VOICE_DIR = $Voice
    AUDIO_CACHE_BASE = "http://<你的服务器局域网IP>:8080/audio"
    AUDIO_UPSTREAM = "http://<本地模型服务器IP>:8106"
    LLM_MAX_TOKENS = "120"
    LLM_WARMUP_SECONDS = "240"
    HARDWARE_TOKEN = ""
    DEVICE_TOKEN = ""
    LLM_PROVIDER = "openai"
    ZONE_URL = "http://127.0.0.1:8013"
    ZONE_MODE = "all"
    XIAOHUI_DEFAULT_CITY = "东莞"
}
Start-Svc "大模型专区" 8013 "$Zone\.venv\Scripts\python.exe" "run_zone.py" $Zone @{}
# 语音服务：统一交给 start_voice.ps1（内含单实例锁 + 完整环境变量），
# 不要再直接 Start-Svc —— 那样会绕过锁，与 XiaohuiKeepAlive 竞态时叠出多个实例
# （2026-11-26 连续 OOM 的真因，见交接文档 §8）。
if (Test-Port 8000) {
    Write-Log "[skip] 语音服务 (8000)"
} else {
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$Tools\start_voice.ps1"
    ) -WindowStyle Hidden
    Write-Log "[start] 语音服务 (8000) -> start_voice.ps1（带单实例锁）"
}
if (Test-Watchdog "zone_watchdog") { Write-Log "[skip] 专区守护" }
else { Start-Process -FilePath "$Zone\.venv\Scripts\python.exe" -ArgumentList "$Tools\zone_watchdog.py" -WindowStyle Hidden; Write-Log "[start] 专区守护" }

if (Test-Watchdog "voice_watchdog") { Write-Log "[skip] 语音守护" }
else { Start-Process -FilePath "$Zone\.venv\Scripts\python.exe" -ArgumentList "$Tools\voice_watchdog.py" -WindowStyle Hidden; Write-Log "[start] 语音守护" }

Write-Log "===== 完成 ====="