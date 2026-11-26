# 启动语音服务（带齐环境变量），已监听 8000 则跳过
param([switch]$Force)

$Voice = "C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server"
$Py = "$Voice\.venv\Scripts\python.exe"
$LockFile = "$Voice\tmp\voice-start.lock"

function Port-Listening([int]$port) {
    return [bool](netstat -ano | Select-String ":$port\s.*LISTENING")
}

if (-not $Force -and (Port-Listening 8000)) { "voice 已在运行 (8000)"; exit 0 }

# —— 单实例锁 ——
# 2026-11-26 事故：手动重启与 XiaohuiKeepAlive 同时触发，3~4 个语音实例并行加载
# torch/FunASR，各自 1.3~5.7GB 提交，把整机提交内存吃穿，DSH 外壳反复 OOM。
#
# 锁以「时间窗口」为准（300 秒），不再依赖 pid 是否存活：
# 一次启动可能耗时 2~3 分钟，期间旧 pid 若已换成新进程，靠 pid 判断会误放行。
# -Force 表示人工干预，跳过锁；自动触发（KeepAlive / 开机）必须遵守锁。
if ((-not $Force) -and (Test-Path $LockFile)) {
    try {
        $rec = Get-Content -LiteralPath $LockFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $age = ((Get-Date) - [datetime]$rec.at).TotalSeconds
        if ($age -lt 300) {
            "voice 启动窗口内（$([int]$age)s 前已触发，记录 pid=$($rec.pid)），跳过本次启动"
            exit 0
        }
    } catch {}
}

if (-not (Test-Path $Py)) { throw "语音服务 venv 缺失: $Py" }

@{ pid = 0; at = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content -LiteralPath $LockFile -Encoding UTF8

$env:USERPROFILE        = "$Voice\.home"
$env:HOME               = "$Voice\.home"
$env:MODELSCOPE_CACHE   = "$Voice\.mscache"
$env:HF_HOME            = "$Voice\.hfhome"
$env:PATH               = "$Voice\.venv\Scripts;" + $env:PATH
$env:PYTHONIOENCODING   = "utf-8"
$env:PYTHONUTF8         = "1"
$env:HARDWARE_TOKEN     = "<REDACTED>"
$env:CONSOLE_URL        = "http://127.0.0.1:8080"
$env:ZONE_MODE          = "all"
# 全部对话走云端大模型（专区 → DeepSeek API）：不再把问候/工具意图分流给本地小模型。
# 想恢复分流：设为 0。
$env:ZONE_ALL_CLOUD     = "1"
$env:ZONE_URL           = "http://127.0.0.1:8013"
$env:ZONE_TIMEOUT       = "8"
$env:KB_URL             = "http://127.0.0.1:8077"
$env:MEMORY_USER_ID     = "default"
# V1.2 阶段一：多句有序并发预合成（2 路）。设为 1 即回退串行。
$env:TTS_CONCURRENCY    = "2"

Set-Location $Voice
$child = Start-Process -FilePath $Py -ArgumentList "app.py" -WorkingDirectory $Voice -NoNewWindow -PassThru
@{ pid = $child.Id; at = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content -LiteralPath $LockFile -Encoding UTF8
"voice 已启动 PID $($child.Id)"
$child.WaitForExit()
