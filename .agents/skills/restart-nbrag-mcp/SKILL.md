---
name: restart-nbrag-mcp
description: Use when nbrag MCP server code, tool docstrings, skills, ingestion, search behavior, or configuration changed and port 9101 must serve the latest local code before MCP validation.
---

# Restart nbrag MCP

Use this skill after changing `D:/codes/nbrag` MCP behavior and before validating through MCP tools. The goal is to make sure `http://127.0.0.1:9101/mcp` is served by the latest local code.

## Command

Run the dedicated PowerShell restart script:

```powershell
powershell -ExecutionPolicy Bypass -File D:/codes/nbrag/.agents/skills/restart-nbrag-mcp/scripts/restart.ps1
```

Optional dry-run:

```powershell
powershell -ExecutionPolicy Bypass -File D:/codes/nbrag/.agents/skills/restart-nbrag-mcp/scripts/restart.ps1 -DryRun
```

## What the script does

1. Finds and kills any live process occupying port `9101`
2. Starts `D:/codes/nbrag/scripts/start_http_rag_mcp.py` in background using `D:/ProgramData/miniconda3/envs/py312/python.exe`
3. Writes stdout/stderr logs under `D:/codes/nbrag/.tmp/nbrag-mcp-runlogs/`
4. Waits until port `9101` is listening, then exits successfully

## Failure Handling

If the script reports that port `9101` is still occupied, the old process did not die cleanly. Inspect the listed PID and rerun the script.

If the script reports startup timeout or early exit, read the stderr log path printed by the script. Fix the import, config, dependency, or runtime error, then rerun the same command.

After restart succeeds, verify the changed behavior with a real MCP call such as `nbrag_stats` or the specific tool you edited.
