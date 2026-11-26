# 扩大页面文件，把「提交内存上限」从 ~32GB 抬到 ~48GB
#
# 背景（2026-11-26 多次崩机）：
#   本机 16GB 物理内存 + D 盘页面文件 8GB~16GB → 提交上限只有 ~32GB。
#   语音服务单实例正常 2.7GB 提交、异常时能到 5.7GB；一旦并发起了 2~4 个实例，
#   提交内存就被打穿，随后 pwsh / DSH 外壳 / .NET 运行时接连 OOM 崩溃
#   （报 OutOfMemoryException、crashpad not connected、0xFFFF7003）。
#
# 本脚本把 D 盘页面文件改为 初始 16GB / 最大 32GB：
#   提交上限 ≈ 物理 16GB + 32GB = 48GB，给峰值留出余量。
#
# 注意：注册表写入后**需要重启才生效**。D 盘当前可用空间足够（>50GB）。
# 副作用：D 盘会被 pagefile.sys 占用最多 32GB（按需增长，不是一次性写满）。

$ErrorActionPreference = "Continue"
$reg = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
$want = "D:\pagefile.sys 16384 32768"

"=== 修改前 ==="
$before = (Get-ItemProperty $reg -Name PagingFiles -ErrorAction SilentlyContinue).PagingFiles
"PagingFiles: " + ($before -join " | ")

Set-ItemProperty -Path $reg -Name "PagingFiles" -Value @($want) -Type MultiString
"已写入: $want"

$after = (Get-ItemProperty $reg -Name PagingFiles -ErrorAction SilentlyContinue).PagingFiles
"=== 修改后 ==="
"PagingFiles: " + ($after -join " | ")

"D 盘可用: " + [math]::Round((Get-PSDrive D).Free/1GB, 1) + " GB"
"生效方式: 重启后生效（重启后提交上限约 48GB）"
