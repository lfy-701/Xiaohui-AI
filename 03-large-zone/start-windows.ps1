# 小慧大模型专区 · 前台启动（调试用）
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) { throw "未找到 .env，请先运行 .\install-windows.ps1" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "未找到 .venv，请先运行 .\install-windows.ps1" }

Write-Host "启动大模型专区：http://127.0.0.1:8013/   （Ctrl+C 停止）"
& .\.venv\Scripts\python.exe run_zone.py
