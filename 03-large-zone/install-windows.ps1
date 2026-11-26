# 小慧大模型专区 · Windows 安装脚本
# 用法（在解压目录打开 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
#   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 -IndexUrl https://pypi.org/simple
param(
    [string]$IndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

Write-Host "=============================================="
Write-Host " 小慧大模型专区 · 安装（独立进程 / 8013）"
Write-Host "=============================================="

function Resolve-Python311 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 --version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return @{ Exe = "py"; Args = @("-3.11") } }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $version = (& python --version 2>&1) -join " "
        if ($version -match "3\.11") { return @{ Exe = "python"; Args = @() } }
    }
    throw "未找到 Python 3.11。请先安装 https://www.python.org/downloads/release/python-3119/，安装时勾选 Add to PATH。"
}

$python = Resolve-Python311
$pythonExe = $python.Exe
$pythonArgs = @($python.Args)
Write-Host "[1/4] Python 3.11 可用：$pythonExe $($pythonArgs -join ' ')"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[2/4] 创建独立虚拟环境 .venv ..."
    & $pythonExe @pythonArgs -m venv .venv
} else {
    Write-Host "[2/4] 复用已有 .venv"
}

Write-Host "[3/4] 安装依赖（镜像：$IndexUrl）..."
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --upgrade pip --index-url $IndexUrl
if ($LASTEXITCODE -ne 0) { throw "pip 升级失败" }
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt --index-url $IndexUrl
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

Write-Host "[4/4] 准备 .env ..."
$envPath = Join-Path $Root ".env"
if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $Root ".env.example") $envPath
    Write-Host "  已从 .env.example 创建 .env"
}

$content = [System.IO.File]::ReadAllText($envPath)
$token = ""
if ($content -match "(?m)^CONSOLE_TOKEN=\s*$") {
    $token = [guid]::NewGuid().ToString("N")
    $content = [regex]::Replace($content, "(?m)^CONSOLE_TOKEN=.*$", "CONSOLE_TOKEN=$token")
} elseif ($content -notmatch "(?m)^CONSOLE_TOKEN=") {
    $token = [guid]::NewGuid().ToString("N")
    $content = $content.TrimEnd() + "`r`nCONSOLE_TOKEN=$token`r`n"
}
[System.IO.File]::WriteAllText($envPath, $content, (New-Object System.Text.UTF8Encoding -ArgumentList $false))

Write-Host ""
Write-Host "安装完成。下一步：" -ForegroundColor Green
Write-Host "  1) 编辑 .env，填入 DEEPSEEK_API_KEY"
Write-Host "  2) 运行 .\start-windows.ps1          （前台启动，调试用）"
Write-Host "     或 .\start-background.ps1         （后台启动）"
if ($token) {
    Write-Host ""
    Write-Host "  本次生成的控制台令牌：$token" -ForegroundColor Yellow
    Write-Host "  打开控制台时输入它；也可以稍后自己改 .env 里的 CONSOLE_TOKEN。"
}
Write-Host ""
Write-Host "  访问地址：http://127.0.0.1:8013/"
Write-Host "  局域网/Tailscale：http://<本机IP>:8013/"
Write-Host ""
Write-Host "  如需其他机器访问，管理员 PowerShell 执行："
Write-Host "  New-NetFirewallRule -DisplayName 'Xiaohui Large Zone 8013' -Direction Inbound -Protocol TCP -LocalPort 8013 -Action Allow"
