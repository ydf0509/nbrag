---
name: restart-nbrag-mcp
description: Use when nbrag MCP server code, tool docstrings, skills, ingestion, search behavior, or configuration changed and port 9101 must serve the latest local code before MCP validation.
---

# 注意
如果你是在trae中，你重启了nbrag mcp服务，不能在当前会话中继续调用nbrag mcp工具，因为链接断开了。
你需要询问让用户去手动刷新mcp连接。

# Restart nbrag MCP

Use this skill after changing `D:/codes/nbrag` MCP behavior and before validating through MCP tools. The goal is to make sure `http://127.0.0.1:9101/mcp` is served by the latest local code.

## Command

Run the dedicated PowerShell restart script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:/codes/nbrag/.agents/skills/restart-nbrag-mcp/scripts/restart.ps1
```

Optional dry-run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:/codes/nbrag/.agents/skills/restart-nbrag-mcp/scripts/restart.ps1 -DryRun
```

`-NoProfile` skips loading the user PowerShell profile (including conda hooks). The script creates and triggers a one-time Task Scheduler task, so the Task Scheduler directly owns the long-running Python process and the calling terminal can return immediately.

## What the script does

1. Finds and kills any live process occupying port `9101`
2. Creates and triggers a one-time Task Scheduler task that directly starts `D:/codes/nbrag/scripts/start_http_rag_mcp.py` using `D:/ProgramData/miniconda3/envs/py312/python.exe`
3. Records the task name and restart metadata in `D:/codes/nbrag/.tmp/nbrag-mcp-runlogs/last-restart.json`
4. Exits without waiting for port `9101`, preventing the caller from blocking on the long-running MCP process

## Failure Handling

If the script reports that port `9101` is still occupied, the old process did not die cleanly. Inspect the listed PID and rerun the script.

If the server is not reachable after restart, inspect the task named in `last-restart.json` with `schtasks.exe /Query /TN <task_name> /V /FO LIST`, then fix its reported failure before rerunning the script.

After restart succeeds, ask the user to refresh the MCP connection before validating through MCP tools.
