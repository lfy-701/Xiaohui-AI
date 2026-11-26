<#
  小慧固件烧录脚本（ESP32-S3，COM4）
  用法：powershell -ExecutionPolicy Bypass -File tools\flash_firmware.ps1 [-Port COM4] [-Baud 460800]
  说明：复用 idf_tools.py export 注入工具链环境，避免手工拼 PATH。
#>
param(
  [string]$Port   = "COM4",
  [string]$Baud   = "460800",
  [string]$ProjectDir = "D:\xiaozhi-esp32-2.5.2",
  [string]$IdfPath    = "D:\esp\v6.1\esp-idf",
  [string]$IdfTools   = "C:\Espressif",
  [string]$PyExe      = "C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$env:IDF_PATH = $IdfPath
$env:IDF_TOOLS_PATH = $IdfTools

if (-not (Test-Path $PyExe)) { throw "python not found: $PyExe" }
if (-not (Test-Path (Join-Path $IdfPath "tools\idf.py"))) { throw "idf.py not found under $IdfPath" }
if (-not (Test-Path $ProjectDir)) { throw "project not found: $ProjectDir" }

Write-Host "[1/3] exporting toolchain env ..."
# idf_tools.py 会往 stderr 打无害警告（如 PATH 里 ninja 版本），不能因此中断
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$kv = & $PyExe (Join-Path $IdfPath "tools\idf_tools.py") export --format key-value 2>&1
$ErrorActionPreference = $prevEap
foreach ($line in $kv) {
  if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    $name = $Matches[1]
    $val  = $Matches[2].Trim()
    if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Substring(1, $val.Length - 2) }
    Set-Item -Path "env:$name" -Value $val
  }
}
# 本机没有标准的 C:\Espressif\python_env\idf6.1_py3.10_env，实际 venv 在 tools\python\v6.1\venv，
# 必须显式指过去，否则 idf.py 报 "python.exe doesn't exist"
$env:IDF_PYTHON_ENV_PATH = Split-Path (Split-Path $PyExe -Parent) -Parent
$env:PYTHONUTF8 = "1"

Write-Host "[2/3] port check $Port ..."
if (-not ([System.IO.Ports.SerialPort]::GetPortNames() -contains $Port)) { throw "$Port 不存在，请检查 USB" }

Write-Host "[3/3] flashing $Port @ $Baud ..."
Push-Location $ProjectDir
try {
  & $PyExe (Join-Path $IdfPath "tools\idf.py") -p $Port -b $Baud flash
  $code = $LASTEXITCODE
} finally {
  Pop-Location
}
if ($code -ne 0) { Write-Host "FLASH FAILED exit=$code"; exit $code }
Write-Host "FLASH OK"
