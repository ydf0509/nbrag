---
name: restart-process
description: Restart any running Python script by its absolute path — kills the old process tree (including children) and relaunches with a specified interpreter. Invoke when user asks to restart/kill a script that may have been started from any working directory, or when a long-running process needs a clean restart after code changes.
---

# Restart Process

Restart any running Python script by absolute path. Handles scripts started from **any** working directory (relative path, partial path, or absolute path).

## When to Invoke

- User asks to restart/kill a script identified by its file path
- A long-running process (HTTP server, worker, watcher) needs a clean restart after code/config changes
- A process was started from an unknown or different working directory and you need to find and restart it

## How It Works

The script uses `psutil` to match processes by resolving the script argument in each process's `cmdline()` against its `cwd()`, so it catches all three launch styles:

| Launch command | Process cwd | Resolved to |
|---|---|---|
| `python mainxx.py` | `D:\codes\proj1` | `D:\codes\proj1\mainxx.py` |
| `python proj1/mainxx.py` | `D:\codes` | `D:\codes\proj1\mainxx.py` |
| `python D:/codes/proj1/mainxx.py` | anywhere | `D:/codes/proj1/mainxx.py` |

All path comparisons are case-insensitive and slash-normalized (Windows).
On Windows, relaunch first tries nohup-style detached flags (`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB`) so HTTP services keep running after the invoking shell/Codex command exits. If the parent Job Object denies `CREATE_BREAKAWAY_FROM_JOB`, it falls back to the same detached flags without breakaway instead of failing startup.

## Usage

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py <script_path> --python <python_exe> [options]
```

### Options

| Flag | Required | Description |
|---|---|---|
| `script_path` | Yes | Absolute path to the target script |
| `--python` | Yes | Python interpreter to use for relaunch |
| `--args` | No | Extra arguments for the script (space-separated) |
| `--cwd` | No | Working directory for relaunch (default: script's directory) |
| `--wait-port` | No | Wait for this port to be connectable before declaring success |
| `--log-dir` | No | Log output directory (default: `tmp/restart-logs/`) |
| `--dry-run` | No | Show what would be killed/started without executing |
| `--kill-only` | No | Kill without restarting |

### Examples

**HTTP service restart** (script listens on a TCP port — use `--wait-port` to block until ready):

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/nbrag/scripts/start_http_rag_mcp.py --python D:/ProgramData/miniconda3/envs/py312/python.exe --cwd D:/codes/nbrag --wait-port 9101
```

**Non-service script restart** (no TCP port — do NOT use `--wait-port`, it would timeout):

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/proj1/data_pipeline.py --python D:/ProgramData/miniconda3/envs/py312/python.exe --args "--input data.csv"
```

Dry-run (safe preview):

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/proj1/main.py --python python --args "--port 8000" --dry-run
```

Kill only (no restart):

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/proj1/main.py --python python --kill-only
```

## Kill Behavior

1. **Find** all processes whose resolved script path matches the target.
2. **Collect children** recursively (`proc.children(recursive=True)`) — kills spawned subprocesses too.
3. **terminate** (SIGTERM) → wait 10s → **kill** (SIGKILL) for survivors.

## Requirements

- Python 3.11+
- `psutil` (already in most conda environments)
