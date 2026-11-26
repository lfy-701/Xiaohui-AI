# 语音实例内存守卫：清理「占内存大但没绑定端口」的残留 python
#
# 用途：配合 XiaohuiKeepAlive（每 5 分钟）一起跑，防止重启竞态/异常退出留下的
# 残留语音实例越积越多（每个 1.3~5.7GB 提交），把提交内存吃穿导致整机 OOM。
#
# 安全规则（只动这一种进程）：
#   1. 进程名 python*；
#   2. 提交内存 > 阈值（默认 1GB，正常服务 2.7GB 也可能命中，所以还要看第 3 条）；
#   3. **不持有任何 LISTENING 端口** —— 真正在提供服务的实例都有端口，不会被误杀。
#
# 输出写入 logs/mem-guard.log，便于事后核对。

param([int]$ThresholdMB = 1024)

$ErrorActionPreference = "Continue"
$LogDir = "D:\AI-Companion-shared\xiaohui-ai\logs"
$Log = Join-Path $LogDir "mem-guard.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-GuardLog($msg) {
    $line = "{0} {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $msg
    $line | Out-File -LiteralPath $Log -Encoding utf8 -Append
}

$listen = @()
try {
    $listen = (netstat -ano | Select-String "LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique)
} catch {
    Write-GuardLog "netstat 读取失败，跳过本轮: $($_.Exception.Message)"
    exit 0
}

$killed = @()
foreach ($p in (Get-Process -Name python* -ErrorAction SilentlyContinue)) {
    if ($p.PrivateMemorySize64 -lt ($ThresholdMB * 1MB)) { continue }
    if ($listen -contains "$($p.Id)") { continue }
    # 启动中的实例还没绑端口，不能误杀：存活不足 180s 的一律跳过
    $age = -1
    try { $age = ((Get-Date) - $p.StartTime).TotalSeconds } catch { $age = -1 }
    if ($age -ge 0 -and $age -lt 180) {
        Write-GuardLog "跳过启动中的实例 PID $($p.Id)（存活 $([int]$age)s）"
        continue
    }
    $mb = [math]::Round($p.PrivateMemorySize64 / 1MB)
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
        $killed += "PID $($p.Id) ($mb MB)"
        Write-GuardLog "已清理残留语音实例 PID $($p.Id)，提交 $mb MB（无监听端口）"
    } catch {
        Write-GuardLog "清理 PID $($p.Id) 失败: $($_.Exception.Message)"
    }
}

# 提交内存水位也记一笔，便于看趋势
try {
    $commit = [math]::Round((Get-Counter '\Memory\Committed Bytes').CounterSamples[0].CookedValue / 1MB)
    $limit = [math]::Round((Get-Counter '\Memory\Commit Limit').CounterSamples[0].CookedValue / 1MB)
    $pct = [math]::Round($commit / $limit * 100)
    Write-GuardLog ("提交内存 {0}/{1} MB ({2}%)，本轮清理 {3} 个" -f $commit, $limit, $pct, $killed.Count)
    if ($pct -ge 90) { Write-GuardLog "警告：提交内存已超过 90%，随时可能 OOM" }
} catch {
    Write-GuardLog ("本轮清理 {0} 个（提交内存读数失败）" -f $killed.Count)
}

if ($killed.Count -gt 0) { "已清理: " + ($killed -join ", ") } else { "无残留实例" }
