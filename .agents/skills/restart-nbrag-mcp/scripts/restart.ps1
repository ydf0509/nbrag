<#
.SYNOPSIS
    Restart nbrag HTTP MCP server on port 9101 in background.
.DESCRIPTION
    1. Stops any process occupying the target port
    2. Starts D:\codes\nbrag\scripts\start_http_rag_mcp.py in background
    3. Waits until the port is listening
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
$oldPidSet = @{}
foreach ($existingPid in $existingPids) {
    $oldPidSet[[string]$existingPid] = $true
}
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
$stdoutLog = Join-Path $RunLogDir "nbrag-mcp-restart-$timestamp.out.log"
$stderrLog = Join-Path $RunLogDir "nbrag-mcp-restart-$timestamp.err.log"

if ($DryRun) {
    Write-Host "  Dry run only" -ForegroundColor Yellow
    Write-Host "  Would run: $Python -u $ServerScript"
    Write-Host "  cwd: $RepoDir"
    exit 0
}

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$RepoDir;$env:PYTHONPATH" } else { $RepoDir }

$arguments = @("-u", $ServerScript)
$proc = Start-Process `
    -FilePath $Python `
    -ArgumentList $arguments `
    -WorkingDirectory $RepoDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Write-Host "  Started PID $($proc.Id)"
Write-Host "  stdout: $stdoutLog"
Write-Host "  stderr: $stderrLog"

$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    $listenerPids = @(Get-PortProcessIds -TargetPort $Port)
    if ($listenerPids) {
        $hasNewPid = $listenerPids -contains $proc.Id
        $hasOldPid = $false
        foreach ($listenerPid in $listenerPids) {
            if ($oldPidSet.ContainsKey([string]$listenerPid)) {
                $hasOldPid = $true
                break
            }
        }

        if ($hasNewPid -and -not $hasOldPid) {
            $restartState = [ordered]@{
                restarted_at = (Get-Date).ToString("s")
                port = $Port
                old_pids = @($existingPids)
                new_pid = $proc.Id
                stdout_log = $stdoutLog
                stderr_log = $stderrLog
            } | ConvertTo-Json -Depth 4
            Set-Content -Path $StateFile -Value $restartState -Encoding UTF8

            Write-Host "  nbrag MCP is listening on http://127.0.0.1:$Port/mcp" -ForegroundColor Green
            Write-Host "  Active listener PID: $($proc.Id)" -ForegroundColor Green
            Write-Host "  restart state: $StateFile" -ForegroundColor Green
            exit 0
        }
    }

    $proc.Refresh()
    if ($proc.HasExited) {
        throw "nbrag MCP exited before listening on port $Port. Check logs: $stdoutLog ; $stderrLog"
    }

    Start-Sleep 2
}

throw "nbrag MCP did not listen on port $Port within 90s. Check logs: $stdoutLog ; $stderrLog"
