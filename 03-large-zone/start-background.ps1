# 小慧大模型专区 · 后台启动
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) { throw "未找到 .env，请先运行 .\install-windows.ps1" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "未找到 .venv，请先运行 .\install-windows.ps1" }

$pidFile = Join-Path $Root "zone.pid"
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -Raw).Trim()
    $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($old) {
        Write-Host "专区已在运行，PID=$oldPid。需要重启请先运行 .\stop-windows.ps1"
        exit 0
    }
    Remove-Item $pidFile -Force
}

$logDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "zone.out.log"
$errLog = Join-Path $logDir "zone.err.log"

$process = Start-Process -FilePath (Join-Path $Root ".venv\Scripts\python.exe") `
    -ArgumentList "run_zone.py" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

$process.Id | Set-Content $pidFile -Encoding ascii
Start-Sleep -Seconds 3
$process.Refresh()
if ($process.HasExited) {
    Write-Host "启动失败，错误日志：" -ForegroundColor Red
    if (Test-Path $errLog) { Get-Content $errLog -Tail 30 }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "已后台启动，PID=$($process.Id)" -ForegroundColor Green
Write-Host "访问：http://127.0.0.1:8013/"
Write-Host "日志：$outLog"
Write-Host "停止：.\stop-windows.ps1"
