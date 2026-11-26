# 重新生成「唤醒应答」音频（按当前角色人设改文案后跑一次）
# 用法：
#   .\gen_wake_reply.ps1                      # 用默认温柔版文案
#   .\gen_wake_reply.ps1 -Text "诶，我在呢！"   # 自定义
#   .\gen_wake_reply.ps1 -Text "在。说吧。" -Voice "Microsoft Kangkang" -Rate -2

param(
    [string]$Text  = "嗯，我在呢，你说。",
    [string]$Voice = "Microsoft Huihui Desktop",
    [int]$Rate     = -1
)

$ErrorActionPreference = "Stop"
$vs  = "C:\Users\53487\Documents\deepseek-harness\default-workspace\voice-server\main\xiaozhi-server"
$out = Join-Path $vs "config\assets\wakeup_words.wav"

Add-Type -AssemblyName System.Speech
$syn = New-Object System.Speech.Synthesis.SpeechSynthesizer

$target = $syn.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -eq $Voice } | Select-Object -First 1
if (-not $target) {
    $target = $syn.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "zh*" } | Select-Object -First 1
    Write-Host "指定的语音不可用，改用: $($target.VoiceInfo.Name)"
}

$syn.SelectVoice($target.VoiceInfo.Name)
$syn.Rate = $Rate

$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    16000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)

$syn.SetOutputToWaveFile($out, $fmt)
$syn.Speak($Text)
$syn.SetOutputToNull()
$syn.Dispose()

# 清空缓存，确保下次唤醒用新音频
Set-Content -Path (Join-Path $vs "data\.wakeup_words.yaml") -Value "" -Encoding UTF8

$kb = [math]::Round((Get-Item $out).Length / 1KB, 1)
Write-Host "已生成：$Text"
Write-Host "语音：$($target.VoiceInfo.Name)"
Write-Host "文件：$out  ($kb KB)"
Write-Host "唤醒缓存已清空，下一次唤醒即生效。"
