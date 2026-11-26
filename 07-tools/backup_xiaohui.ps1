# 小慧项目备份脚本
# 用法：powershell -ExecutionPolicy Bypass -File tools\backup_xiaohui.ps1 [-Name "1126备份"]
param(
    [string]$Name = ((Get-Date).ToString("MMdd") + "备份"),
    [string]$DestRoot = "D:\.小慧AI备份"
)

$ErrorActionPreference = "Stop"
$WS      = "C:\Users\53487\Documents\deepseek-harness\default-workspace"
$Voice   = "$WS\voice-server\main\xiaozhi-server"
$Shared  = "D:\AI-Companion-shared\xiaohui-ai"
$Zone    = "D:\xiaohui-large-zone"
$Fw      = "D:\xiaozhi-esp32-2.5.2"
$Dest    = Join-Path $DestRoot $Name

function Copy-Tree([string]$src, [string]$dst, [string[]]$xd, [string[]]$xf) {
    if (-not (Test-Path $src)) { Write-Host "[skip] 不存在: $src"; return }
    $roboArgs = @($src, $dst, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/R:1", "/W:1", "/MT:8")
    if ($xd) { $roboArgs += "/XD"; $roboArgs += $xd }
    if ($xf) { $roboArgs += "/XF"; $roboArgs += $xf }
    & robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy 失败($LASTEXITCODE): $src -> $dst" }
}

Write-Host "===== 备份到 $Dest ====="
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

# 1) 语音服务：代码 + 配置 + data；排除虚拟环境/模型/缓存/日志
Copy-Tree $Voice "$Dest\voice-server" @(".venv","models",".mscache",".hfhome",".home","__pycache__","tmp") @("*.log")

# 2) 控制台：代码 + 静态页；数据单独放一层（方便单独还原某个库）
Copy-Tree "$Shared\console" "$Dest\console" @(".venv","__pycache__") @("*.pyc")
Copy-Tree "$Shared\console\data" "$Dest\console-data" @() @()

# 3) 知识库（长期记忆库在这里）
Copy-Tree "$Shared\kb-service" "$Dest\kb-service" @(".venv","__pycache__") @("*.pyc")

# 4) 大模型专区（.env 含 Key，仅本机备份）
Copy-Tree $Zone "$Dest\large-zone" @(".venv","__pycache__","logs") @("*.pyc")

# 5) 工作区工具脚本 + 文档
Copy-Tree "$WS\tools" "$Dest\tools" @("__pycache__") @("_console_copy.db","*.pyc")
Copy-Tree "$WS\docs"  "$Dest\docs"  @() @()

# 6) 固件：板级代码 + sdkconfig + 已编译 bin（不拷中间产物）
Copy-Tree "$Fw\main\boards\esp32-dog-wangcai" "$Dest\firmware\boards\esp32-dog-wangcai" @() @()
foreach ($f in @("sdkconfig","sdkconfig.defaults")) {
    $p = Join-Path $Fw $f
    if (Test-Path $p) { Copy-Item $p "$Dest\firmware\" -Force }
}
New-Item -ItemType Directory -Path "$Dest\firmware\build" -Force | Out-Null
Get-ChildItem "$Fw\build" -Filter "*.bin" -ErrorAction SilentlyContinue |
    ForEach-Object { Copy-Item $_.FullName "$Dest\firmware\build\" -Force }

# 7) 备份说明
$readme = @"
小慧 AI 机器狗 · $Name  ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))

包含：
  voice-server  语音服务代码 + .config.yaml / data（不含 .venv、models、日志）
  console       控制台代码 + 静态页
  console-data  控制台数据库 console.db（设备/日志/动作序列）
  kb-service    知识库 + 长期记忆库 data\memory.db
  large-zone    大模型专区代码 + .env（含 DeepSeek Key，请勿外传）
  tools         启动/守护/诊断脚本（xiaohui_start_all.ps1 等）
  docs          交接文档
  firmware      板级代码 + sdkconfig + 已编译 bin

恢复要点：
  1. 各服务必须用各自 .venv（Anaconda 没有 uvicorn）
  2. 控制台/知识库/专区要写自己的目录，启动需有写权限
  3. xiaohui_start_all.ps1 必须保持 UTF-8 with BOM
  4. 详细说明见 docs\xiaohui-交接文档-20261126.md
"@
$readme | Out-File (Join-Path $Dest "README-备份说明.txt") -Encoding utf8

# 8) 统计
$allFiles = @(Get-ChildItem $Dest -Recurse -File)
$totalMB = [math]::Round((($allFiles | Measure-Object -Property Length -Sum).Sum) / 1MB, 1)
Write-Host "完成：$($allFiles.Count) 个文件，约 $totalMB MB"
Write-Host "位置：$Dest"
