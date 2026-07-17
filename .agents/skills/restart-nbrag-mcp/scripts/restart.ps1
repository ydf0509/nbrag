<#
.SYNOPSIS
    Restart nbrag HTTP MCP server on port 9101 in background.
.DESCRIPTION
    1. Stops any process occupying the target port
    2. Starts D:\codes\nbrag\scripts\start_http_rag_mcp.py directly through Task Scheduler
    3. Exits immediately after recording the detached task information
#>

param(
    [int]$Port = 9101,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoDir = "D:\codes\nbrag"
$Python = "D:\ProgramData\miniconda3\envs\py312\python.exe"
$ServerScript = "D:\codes\nbrag\scripts\start_http_rag_mcp.py"
$Netstat = Join-Path $env:SystemRoot "System32\netstat.exe"
$RunLogDir = Join-Path (Join-Path $RepoDir ".tmp") "nbrag-mcp-runlogs"
$StateFile = Join-Path $RunLogDir "last-restart.json"

if (Test-Path $StateFile) {
    try {
        $previousState = Get-Content -Path $StateFile -Raw | ConvertFrom-Json
        if ($previousState.task_name) {
            schtasks.exe /Delete /TN $previousState.task_name /F 2>$null | Out-Null
        }
    } catch {
    }
}

function Get-PortProcessIds {
    param([int]$TargetPort)

    $ids = @()

    try {
        $tcpConnections = Get-NetTCPConnection -LocalPort $TargetPort -ErrorAction SilentlyContinue
        foreach ($conn in $tcpConnections) {
            if ($conn.State -ne "TimeWait") {
                $ids += $conn.OwningProcess
            }
        }
    } catch {
        Write-Host "  Get-NetTCPConnection failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    $netstatLines = & $Netstat -ano | Select-String ":$TargetPort"
    foreach ($line in $netstatLines) {
        $parts = ($line.ToString().Trim() -split "\s+")
        if ($parts.Length -ge 5 -and $parts[1] -match ":$TargetPort$") {
            $foundPid = [int]$parts[-1]
            if ($foundPid -ne 0 -and (Get-Process -Id $foundPid -ErrorAction SilentlyContinue)) {
                $ids += $foundPid
            }
        }
    }

    $ids | Sort-Object -Unique | Where-Object { $_ -ne 0 }
}

Write-Host "`n=== [1/2] Stopping existing nbrag MCP on port $Port ===" -ForegroundColor Cyan
$existingPids = Get-PortProcessIds -TargetPort $Port
if ($existingPids) {
    foreach ($procId in $existingPids) {
        Write-Host "  Killing PID $procId"
    }
    if (-not $DryRun) {
        $existingPids | ForEach-Object {
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep 2
        $remaining = Get-PortProcessIds -TargetPort $Port
        if ($remaining) {
            throw "Port $Port is still occupied by PID(s): $($remaining -join ', ')"
        }
        Write-Host "  Old MCP server stopped" -ForegroundColor Green
    }
} else {
    Write-Host "  No existing MCP server found" -ForegroundColor Yellow
}

Write-Host "`n=== [2/2] Starting nbrag HTTP MCP server ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $RunLogDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"

if ($DryRun) {
    Write-Host "  Dry run only" -ForegroundColor Yellow
    Write-Host "  Would schedule directly: $Python -u $ServerScript"
    Write-Host "  cwd: $RepoDir"
    exit 0
}

$taskName = "NBragMcpRestart-$([guid]::NewGuid().ToString('N'))"
$taskCommand = "`"$Python`" -u `"$ServerScript`""

schtasks.exe /Create /TN $taskName /TR "`"$taskCommand`"" /SC ONCE /ST 23:59 /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create detached Task Scheduler task '$taskName'."
}

schtasks.exe /Run /TN $taskName | Out-Null
if ($LASTEXITCODE -ne 0) {
    schtasks.exe /Delete /TN $taskName /F 2>$null | Out-Null
    throw "Failed to start detached Task Scheduler task '$taskName'."
}

Write-Host "  Submitted detached task $taskName"

$restartState = [ordered]@{
    restarted_at = (Get-Date).ToString("s")
    port = $Port
    old_pids = @($existingPids)
    task_name = $taskName
} | ConvertTo-Json -Depth 4
Set-Content -Path $StateFile -Value $restartState -Encoding UTF8

Write-Host "  Task Scheduler directly owns the MCP process; the script exits without waiting for port $Port." -ForegroundColor Green
Write-Host "  restart state: $StateFile" -ForegroundColor Green
