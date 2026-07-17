---
name: restart-traesolo
description: Use when the user asks to restart, relaunch, or kill TRAE SOLO CN, Trae SOLO, or Trae Work from an agent running inside that application.
---

# Restart TRAE SOLO CN

Use this skill when the user asks to restart the standalone TRAE Work desktop application named `TRAE SOLO CN.exe`.

## Verified Method

This method was successfully executed on this machine. The current agent runs within TRAE SOLO, but the actual stop/start work runs from Windows Task Scheduler with the current user's interactive token. It is therefore outside TRAE SOLO's process tree.

## Required Workflow

Do not use `taskkill` followed by `start`, `Start-Process`, Python `Popen`, `wmic`, or `os.startfile()` directly from the agent. Those processes may belong to TRAE SOLO's Job Object and terminate before the relaunch step.

For an actual restart, run exactly this command once:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\codes\nbrag\.agents\skills\restart-traesolo\scripts\install-restart-traesolo-task.ps1"
```

Run it as a short, non-blocking command. Once it prints `task=TRAE-SOLO-Restart started`, do not issue further commands in the old session: it will disconnect about five seconds later.

The installer registers or replaces `TRAE-SOLO-Restart` with the current user's interactive token and immediately starts it. The Task Scheduler process is independent from TRAE SOLO's process tree.

The worker performs these steps:

1. Writes lifecycle events to `D:\codes\nbrag\.tmp\restart-traesolo\restart.log`.
2. Waits five seconds.
3. Stops every `TRAE SOLO CN` process.
4. Waits for all matching processes to exit.
5. Starts `D:\Users\ydf6\AppData\Local\Programs\TRAE SOLO CN\TRAE SOLO CN.exe`.

## After the Restart

When a new TRAE SOLO session becomes available, inspect:

```powershell
Get-Content "D:\codes\nbrag\.tmp\restart-traesolo\restart.log"
```

The expected terminal event is `event=restart_started`. If an `event=error` line exists, report its message before changing the scripts or proposing a different restart mechanism.

## Safe Probe

Use this only before the first actual restart on a different machine, or when diagnosing a Task Scheduler failure. It does not restart TRAE SOLO:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\codes\nbrag\.agents\skills\restart-traesolo\scripts\install-restart-traesolo-task.ps1" -Probe -LogPath "D:\codes\nbrag\.tmp\restart-traesolo\probe.log"
```

Success requires `probe.log` to contain both `event=worker_started` and `event=probe_completed`.

## Scripts

| File | Purpose |
|------|---------|
| `scripts/install-restart-traesolo-task.ps1` | Registers and triggers the independent interactive scheduled task. |
| `scripts/restart-traesolo-worker.ps1` | Logs, stops TRAE SOLO, waits for exit, and launches it again. |

## Failure Boundary

- Do not replace this mechanism with another direct child-process workaround merely because the old chat session disconnects; that disconnection is expected.
- Do not suppress worker logs. The log is the diagnostic source when a restart does not complete.
- Do not run the safe probe before every normal restart; this machine has already passed it.
