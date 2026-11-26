# 直接把分页文件配置写进注册表（权威设置）
$ErrorActionPreference = "Stop"
$log = "$env:TEMP\pagefile_fix.log"
function Log($m) { $m | Tee-Object -FilePath $log -Append }

$reg = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
$want = "D:\pagefile.sys 8192 16384"

Log "=== 修改前 ==="
Log ("PagingFiles: " + ((Get-ItemProperty $reg -Name PagingFiles -ErrorAction SilentlyContinue).PagingFiles -join " | "))

# 强制关闭自动管理
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) {
    $cs | Set-CimInstance -Property @{AutomaticManagedPagefile = $false}
    Log "已关闭自动管理"
}

# 写入 MULTI_SZ
Set-ItemProperty -Path $reg -Name "PagingFiles" -Value @($want) -Type MultiString
Log ("已写入: " + $want)

# 校验
$now = (Get-ItemProperty $reg -Name PagingFiles).PagingFiles
Log ("=== 修改后 PagingFiles: " + ($now -join " | "))
Log ("自动管理: " + (Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile)

# 用 WMI 再补一条，保证系统界面里也能看到
$pf = Get-CimInstance Win32_PageFileSetting
if (-not $pf) {
    try {
        New-CimInstance -ClassName Win32_PageFileSetting -Property @{
            Name = "D:\pagefile.sys"; InitialSize = 8192; MaximumSize = 16384
        } | Out-Null
        Log "WMI 记录已补建"
    } catch { Log ("WMI 补建失败(不影响注册表生效): " + $_.Exception.Message) }
}

Log "完成：重启后 D 盘生效，C 盘 pagefile.sys 自动移除。"
Start-Sleep -Seconds 2
