param(
    [switch]$Probe,
    [string]$LogPath = 'D:\codes\nbrag\.tmp\restart-traesolo\restart.log'
)

$taskName = if ($Probe) { 'TRAE-SOLO-Restart-Probe' } else { 'TRAE-SOLO-Restart' }
$workerPath = Join-Path $PSScriptRoot 'restart-traesolo-worker.ps1'
$mode = if ($Probe) { 'Probe' } else { 'Restart' }
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$workerPath`" -Mode $mode -LogPath `"$LogPath`""
$action = New-ScheduledTaskAction -Execute 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Argument $arguments
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "task=$taskName started"
