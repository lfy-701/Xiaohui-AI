# 小慧大模型专区 · 停止后台进程
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$pidFile = Join-Path $Root "zone.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "没有找到 zone.pid，专区可能未在后台运行。"
    exit 0
}

$zonePid = (Get-Content $pidFile -Raw).Trim()
$process = Get-Process -Id $zonePid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $zonePid -Force
    Write-Host "已停止，PID=$zonePid"
} else {
    Write-Host "进程 $zonePid 已不存在"
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
