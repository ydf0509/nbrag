---
name: restart-nbrag-mcp
description: Restart the local nbrag MCP streamable-http service on port 9101 after changing nbrag MCP/server code, tool docstrings, skills, ingestion/search behavior, or configuration that must be verified through the running MCP server. Use this when AGENTS.md says to run D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py, when the current server may still be serving old code, or before validating newly changed MCP tools through an MCP client.
---

# Restart nbrag MCP

## Workflow

Use this skill after editing nbrag MCP behavior and before verifying it through MCP tools. The goal is to make sure port `9101` is serving the latest local code from `D:/codes/nbrag`.

1. Finish the code or documentation change that affects the MCP runtime.
2. Run the bundled restart script from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/restart-nbrag-mcp/scripts/restart_nbrag_mcp.ps1
```

3. Confirm the script reports a new process id, port `9101`, and log paths.
4. Verify the changed behavior with the relevant MCP call. For tool description changes, inspect the tool metadata or invoke the affected tool with a small, safe request.

## Script Behavior

The script follows the command required by `AGENTS.md`:

```text
D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py
```

It performs these steps:

- Validates the configured Python interpreter and `start_http_rag_mcp.py` exist.
- Stops existing processes whose command line matches `start_http_rag_mcp.py`.
- Checks port `9101`; if another process owns the port, it fails with diagnostics instead of stopping an unrelated process.
- Starts the MCP server hidden in the background.
- Writes stdout/stderr logs under `tmp/nbrag-mcp-logs/`.
- Polls `127.0.0.1:9101` until the service is listening.

## Useful Options

Use `-DryRun` before a risky restart to see what would be stopped and started:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/restart-nbrag-mcp/scripts/restart_nbrag_mcp.ps1 -DryRun
```

Use `-ForcePortOwner` only when you have confirmed that the current owner of port `9101` is disposable:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/restart-nbrag-mcp/scripts/restart_nbrag_mcp.ps1 -ForcePortOwner
```

Override paths only when working from a copied checkout or alternate Python environment:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/restart-nbrag-mcp/scripts/restart_nbrag_mcp.ps1 `
  -PythonExe D:/ProgramData/miniconda3/envs/py312/python.exe `
  -ServerScript D:/codes/nbrag/scripts/start_http_rag_mcp.py `
  -Port 9101
```

## Failure Handling

If the script says another process owns port `9101`, inspect the reported process id and command line before using `-ForcePortOwner`.

If the server exits before the port opens, read the stderr log path printed by the script. Fix the underlying import, config, dependency, or port issue, then rerun the restart script.

If the service starts but MCP validation still shows old behavior, confirm the edited files are under `D:/codes/nbrag`, rerun the script, and verify the MCP client is connected to `http://127.0.0.1:9101`.
