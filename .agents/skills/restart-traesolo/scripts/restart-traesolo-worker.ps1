param(
    [ValidateSet('Probe', 'Restart')]
    [string]$Mode = 'Restart',
    [string]$LogPath = 'D:\codes\nbrag\.tmp\restart-traesolo\restart.log'
)

$logDirectory = Split-Path -Parent $LogPath
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-RestartLog {
    param([string]$Message)
    Add-Content -LiteralPath $LogPath -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff') pid=$PID mode=$Mode $Message" -Encoding utf8
}

try {
    Write-RestartLog "event=worker_started user=$env:USERDOMAIN\\$env:USERNAME session=$((Get-Process -Id $PID).SessionId)"

    if ($Mode -eq 'Probe') {
        Write-RestartLog 'event=probe_completed'
        exit 0
    }

    $traeExecutable = 'D:\Users\ydf6\AppData\Local\Programs\TRAE SOLO CN\TRAE SOLO CN.exe'
    if (-not (Test-Path -LiteralPath $traeExecutable -PathType Leaf)) {
        throw "TRAE SOLO executable not found: $traeExecutable"
    }

    Write-RestartLog 'event=restart_requested'
    Start-Sleep -Seconds 5
    Get-Process -Name 'TRAE SOLO CN' -ErrorAction SilentlyContinue | Stop-Process -Force

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Process -Name 'TRAE SOLO CN' -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
    }

    if (Get-Process -Name 'TRAE SOLO CN' -ErrorAction SilentlyContinue) {
        throw 'TRAE SOLO processes did not exit within 20 seconds'
    }

    Start-Process -FilePath $traeExecutable | Out-Null
    Write-RestartLog 'event=restart_started'
}
catch {
    Write-RestartLog "event=error message=$($_.Exception.Message)"
    exit 1
}
