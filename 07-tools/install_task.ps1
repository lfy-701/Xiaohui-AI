# 注册「小慧服务守护」计划任务：登录时自动启动 supervisor.ps1，常驻巡检
$ErrorActionPreference = "Stop"
$log = "$env:TEMP\xiaohui_task.log"
function Log($m) { $m | Tee-Object -FilePath $log -Append }

$supervisor = "C:\Users\53487\Documents\deepseek-harness\default-workspace\supervisor.ps1"
if (-not (Test-Path $supervisor)) { Log "supervisor.ps1 不存在: $supervisor"; exit 1 }

$name = "XiaohuiServices"

# 先删旧任务
try { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue } catch {}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $supervisor + '"')

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "小慧控制台与语音服务守护：登录后常驻，服务掉线自动拉起" -Force | Out-Null

Log "已注册任务: $name"

# 立刻启动一次（服务已在跑时它只会巡检）
Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 3

$info = Get-ScheduledTask -TaskName $name
$state = (Get-ScheduledTaskInfo -TaskName $name)
Log ("状态: " + $info.State)
Log ("上次结果: " + $state.LastTaskResult)
Log "完成"
