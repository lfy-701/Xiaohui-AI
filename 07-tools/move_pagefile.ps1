# 把页面文件从 C 盘移到 D 盘（需管理员）
# 只改系统设置，不重启、不动任何服务；重启后生效。

$ErrorActionPreference = "Stop"
$log = "$env:TEMP\pagefile_move.log"
function Log($m) { $m | Tee-Object -FilePath $log -Append }

Log "=== 当前设置 ==="
$auto = (Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile
Log ("自动管理: " + $auto)
Get-CimInstance Win32_PageFileSetting | ForEach-Object {
    Log ("  现有: " + $_.Name + "  初始 " + $_.InitialSize + " MB  最大 " + $_.MaximumSize + " MB")
}

# 1) 关闭自动管理
if ($auto) {
    $cs = Get-CimInstance Win32_ComputerSystem
    $cs | Set-CimInstance -Property @{AutomaticManagedPagefile = $false}
    Log "已关闭自动管理"
} else {
    Log "自动管理本来就是关闭的"
}

# 2) 删除 C 盘页面文件设置
Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like "C:*" } | ForEach-Object {
    Remove-CimInstance -InputObject $_
    Log "已移除 " + $_.Name
}

# 3) 在 D 盘创建（8 GB 初始 / 16 GB 最大）
$exists = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like "D:*" }
if (-not $exists) {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name        = "D:\pagefile.sys"
        InitialSize = 8192
        MaximumSize = 16384
    } | Out-Null
    Log "已在 D 盘创建页面文件设置（8192 / 16384 MB）"
} else {
    $exists | Set-CimInstance -Property @{InitialSize = 8192; MaximumSize = 16384}
    Log "已更新 D 盘页面文件大小"
}

Log "=== 修改后 ==="
(Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile | ForEach-Object { Log ("自动管理: " + $_) }
Get-CimInstance Win32_PageFileSetting | ForEach-Object {
    Log ("  " + $_.Name + "  初始 " + $_.InitialSize + " MB  最大 " + $_.MaximumSize + " MB")
}
Log "完成。重启后生效；C 盘会在重启时释放 pagefile.sys 占用的空间。"
Log "日志: $log"
Start-Sleep -Seconds 3
