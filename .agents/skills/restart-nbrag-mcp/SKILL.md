---
name: restart-nbrag-mcp
description: Restart the local nbrag MCP streamable-http service on port 9101 after changing nbrag MCP/server code, tool docstrings, skills, ingestion/search behavior, or configuration that must be verified through the running MCP server. Use this when AGENTS.md says to run D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py, when the current server may still be serving old code, or before validating newly changed MCP tools through an MCP client.
---

# Restart nbrag MCP

## Workflow

Use this skill after editing nbrag MCP behavior and before verifying it through MCP tools. The goal is to make sure port `9101` is serving the latest local code from `D:/codes/nbrag`.

1. Finish the code or documentation change that affects the MCP runtime.
2. Use the **restart_process** skill to restart `D:/codes/nbrag/scripts/start_http_rag_mcp.py`:

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/nbrag/scripts/start_http_rag_mcp.py --python D:/ProgramData/miniconda3/envs/py312/python.exe --cwd D:/codes/nbrag --wait-port 9101
```

> ⚠️ `--cwd D:/codes/nbrag` is required — the script imports `my_load_config` and loads `nbrag_config.yaml` from the project root, not from `scripts/`.

3. Confirm the script reports a new process id, port `9101`, and log paths.
4. Verify the changed behavior with the relevant MCP call. For tool description changes, inspect the tool metadata or invoke the affected tool with a small, safe request.

## Why restart_process

The `restart_process` skill is the general-purpose process restart tool. It uses `psutil` to match processes by absolute script path (resolving relative paths against each process's `cwd()`), recursively kills child processes, relaunches with a specified interpreter, and optionally waits for a TCP port to confirm readiness.

See `.agents/skills/restart_process/SKILL.md` for full options (`--dry-run`, `--kill-only`, `--args`, `--cwd`, `--log-dir`).

## Useful Options

Dry-run (safe preview, see what would be killed/started):

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/nbrag/scripts/start_http_rag_mcp.py --python D:/ProgramData/miniconda3/envs/py312/python.exe --cwd D:/codes/nbrag --wait-port 9101 --dry-run
```

Kill only (no restart):

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe .agents/skills/restart_process/scripts/restart_process.py D:/codes/nbrag/scripts/start_http_rag_mcp.py --python D:/ProgramData/miniconda3/envs/py312/python.exe --kill-only
```

## Failure Handling

If the script reports `port 9101 timeout`, the server exited before binding the port. Read the stderr log under `tmp/restart-logs/` printed by the script. Fix the underlying import, config, dependency, or port issue, then rerun the restart command.

If the service starts but MCP validation still shows old behavior, confirm the edited files are under `D:/codes/nbrag`, rerun the restart, and verify the MCP client is connected to `http://127.0.0.1:9101`.
