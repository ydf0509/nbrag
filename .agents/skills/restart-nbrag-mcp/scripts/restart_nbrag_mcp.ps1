#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$PythonExe = "D:/ProgramData/miniconda3/envs/py312/python.exe",
    [string]$ServerScript = "D:/codes/nbrag/scripts/start_http_rag_mcp.py",
    [int]$Port = 9101,
    [int]$ReadyTimeoutSeconds = 30,
    [int]$StopTimeoutSeconds = 10,
    [switch]$DryRun,
    [switch]$ForcePortOwner
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-PathText {
    param([string]$PathText)
    return $PathText.Replace("\", "/").ToLowerInvariant()
}

function Resolve-ExistingFile {
    param(
        [string]$PathText,
        [string]$Label
    )

    $resolved = Resolve-Path -LiteralPath $PathText -ErrorAction SilentlyContinue
    if (-not $resolved) {
        throw "$Label not found: $PathText"
    }

    return $resolved.Path
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)

    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        return $proc.CommandLine
    }
    catch {
        return $null
    }
}

function Test-NbragServerProcess {
    param(
        [int]$ProcessId,
        [string]$ExpectedScript
    )

    $commandLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if (-not $commandLine) {
        return $false
    }

    $normalizedCommand = Normalize-PathText $commandLine
    $normalizedScript = Normalize-PathText $ExpectedScript
    return $normalizedCommand.Contains($normalizedScript) -or $normalizedCommand.Contains("start_http_rag_mcp.py")
}

function Get-PortListenerPids {
    param([int]$LocalPort)

    $pids = @{}
    $command = Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue
    if ($command) {
        try {
            foreach ($listener in @(Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue)) {
                $ownerPid = [int]$listener.OwningProcess
                if ($ownerPid -gt 0) {
                    $pids[$ownerPid] = $true
                }
            }
        }
        catch {
            Write-Host "Get-NetTCPConnection failed; falling back to netstat -ano."
        }
    }

    if ($pids.Count -eq 0) {
        $localPortPattern = "[:.]$LocalPort$"
        foreach ($line in @(netstat -ano | Select-String -Pattern "LISTENING")) {
            $parts = @($line.ToString() -split "\s+" | Where-Object { $_ })
            if ($parts.Count -ge 5 -and $parts[0] -eq "TCP" -and $parts[1] -match $localPortPattern -and $parts[3] -eq "LISTENING") {
                $ownerPid = 0
                if ([int]::TryParse($parts[4], [ref]$ownerPid) -and $ownerPid -gt 0) {
                    $pids[$ownerPid] = $true
                }
            }
        }
    }

    return @($pids.Keys | ForEach-Object { [int]$_ })
}

function Test-PortOpen {
    param([int]$LocalPort)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $LocalPort)
        if (-not $task.Wait(500)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Stop-TargetProcess {
    param(
        [int]$ProcessId,
        [string]$Reason,
        [int]$TimeoutSeconds
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return
    }

    if ($DryRun) {
        Write-Host "[dry-run] Would stop PID $ProcessId ($($process.ProcessName)): $Reason"
        return
    }

    Write-Host "Stopping PID $ProcessId ($($process.ProcessName)): $Reason"
    Stop-Process -Id $ProcessId -Force

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "Process $ProcessId did not exit within $TimeoutSeconds seconds."
}

function Repair-ProcessPathEnvironment {
    $processEnv = [System.Environment]::GetEnvironmentVariables("Process")
    $pathKeys = @($processEnv.Keys | Where-Object { [string]::Equals([string]$_, "Path", [System.StringComparison]::OrdinalIgnoreCase) })

    if ($pathKeys.Count -le 1) {
        return
    }

    $pathValue = $null
    foreach ($key in @("Path", "PATH")) {
        if ($processEnv.Contains($key) -and $processEnv[$key]) {
            $pathValue = [string]$processEnv[$key]
            break
        }
    }

    foreach ($key in $pathKeys) {
        [System.Environment]::SetEnvironmentVariable([string]$key, $null, "Process")
    }
    if ($pathValue) {
        [System.Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
    }
}

$pythonPath = Resolve-ExistingFile -PathText $PythonExe -Label "Python interpreter"
$serverPath = Resolve-ExistingFile -PathText $ServerScript -Label "nbrag MCP startup script"
$repoRoot = Split-Path -Parent (Split-Path -Parent $serverPath)
$logDir = Join-Path $repoRoot "tmp/nbrag-mcp-logs"
$targetPids = @{}

Write-Host "Restart target:"
Write-Host "  Python: $pythonPath"
Write-Host "  Script: $serverPath"
Write-Host "  Port:   $Port"

$normalizedServerPath = Normalize-PathText $serverPath
$matchingProcesses = @(Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%start_http_rag_mcp.py%'" -ErrorAction SilentlyContinue | Where-Object {
    if (-not $_.CommandLine) {
        return $false
    }
    $commandLine = Normalize-PathText $_.CommandLine
    return $commandLine.Contains($normalizedServerPath) -or $commandLine.Contains("start_http_rag_mcp.py")
})

foreach ($match in $matchingProcesses) {
    $targetPids[[int]$match.ProcessId] = "command line matches start_http_rag_mcp.py"
}

$listenerPids = @(Get-PortListenerPids -LocalPort $Port)
if ($listenerPids.Count -gt 0) {
    Write-Host "Port $Port listener PID(s): $($listenerPids -join ', ')"
}

foreach ($ownerPid in $listenerPids) {
    if ($targetPids.ContainsKey($ownerPid)) {
        continue
    }

    $commandLine = Get-ProcessCommandLine -ProcessId $ownerPid
    if (Test-NbragServerProcess -ProcessId $ownerPid -ExpectedScript $serverPath) {
        $targetPids[$ownerPid] = "owns port $Port and matches nbrag startup script"
        continue
    }

    $process = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
    $processName = if ($process) { $process.ProcessName } else { "unknown" }
    if ($ForcePortOwner) {
        $targetPids[$ownerPid] = "owns port $Port; -ForcePortOwner was supplied"
        continue
    }

    Write-Host "Port $Port is owned by PID $ownerPid ($processName)."
    if ($commandLine) {
        Write-Host "Command line: $commandLine"
    }
    throw "Refusing to stop an unrelated port owner. Re-run with -ForcePortOwner only after confirming it is safe."
}

foreach ($targetPid in @($targetPids.Keys)) {
    Stop-TargetProcess -ProcessId ([int]$targetPid) -Reason $targetPids[$targetPid] -TimeoutSeconds $StopTimeoutSeconds
}

if ($DryRun) {
    Write-Host "[dry-run] Would start: $pythonPath $serverPath"
    exit 0
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdoutLog = Join-Path $logDir "nbrag-mcp-$stamp.out.log"
$stderrLog = Join-Path $logDir "nbrag-mcp-$stamp.err.log"

Repair-ProcessPathEnvironment
Write-Host "Starting nbrag MCP HTTP service..."
$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @($serverPath) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        Write-Host "stdout log: $stdoutLog"
        Write-Host "stderr log: $stderrLog"
        throw "nbrag MCP process exited early with code $($process.ExitCode)."
    }

    if (Test-PortOpen -LocalPort $Port) {
        Write-Host "nbrag MCP HTTP service is listening."
        Write-Host "  PID:        $($process.Id)"
        Write-Host "  URL:        http://127.0.0.1:$Port"
        Write-Host "  stdout log: $stdoutLog"
        Write-Host "  stderr log: $stderrLog"
        exit 0
    }

    Start-Sleep -Milliseconds 500
}

Write-Host "stdout log: $stdoutLog"
Write-Host "stderr log: $stderrLog"
throw "Timed out waiting for port $Port after $ReadyTimeoutSeconds seconds."
