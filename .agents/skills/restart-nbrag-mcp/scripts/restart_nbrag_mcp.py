#!/usr/bin/env python
"""Restart the local nbrag MCP HTTP service on port 9101."""

from __future__ import annotations

import argparse
import csv
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_PYTHON = "D:/ProgramData/miniconda3/envs/py312/python.exe"
DEFAULT_SCRIPT = "D:/codes/nbrag/scripts/start_http_rag_mcp.py"
DEFAULT_PORT = 9101


def norm(text: str) -> str:
    return text.replace("\\", "/").lower()


def existing_file(path: str, label: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise SystemExit(f"{label} not found: {path}")
    return p


def run_text(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return ""


def list_processes() -> dict[int, str]:
    """Return pid -> command line using Windows built-in tools."""
    try:
        import psutil

        processes: dict[int, str] = {}
        for proc in psutil.process_iter(["pid"]):
            try:
                command = " ".join(proc.cmdline())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            if command:
                processes[proc.pid] = command
        if processes:
            return processes
    except Exception:
        pass

    output = run_text(["wmic", "process", "get", "ProcessId,CommandLine", "/FORMAT:CSV"])
    processes: dict[int, str] = {}
    if output:
        for row in csv.DictReader(line for line in output.splitlines() if line.strip()):
            try:
                pid = int(row.get("ProcessId") or 0)
            except ValueError:
                continue
            command = row.get("CommandLine") or ""
            if pid and command:
                processes[pid] = command
    if processes:
        return processes

    ps = "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    output = run_text(["powershell", "-NoProfile", "-Command", ps])
    if not output:
        return processes

    import json

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return processes
    if isinstance(data, dict):
        data = [data]
    for item in data:
        command = item.get("CommandLine") or ""
        pid = int(item.get("ProcessId") or 0)
        if pid and command:
            processes[pid] = command
    return processes


def port_listener_pids(port: int) -> set[int]:
    output = run_text(["netstat", "-ano", "-p", "tcp"])
    pids: set[int] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].rsplit(":", 1)[-1] == str(port):
                try:
                    pids.add(int(parts[4]))
                except ValueError:
                    pass
    return pids


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def stop_pid(pid: int, reason: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] Would stop PID {pid}: {reason}")
        return
    print(f"Stopping PID {pid}: {reason}")
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def subprocess_creation_flags() -> int:
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    return flags | breakaway


def start_server_process(
    python: Path,
    script: Path,
    repo_root: Path,
    stdout_log: Path,
    stderr_log: Path,
    env: dict[str, str],
) -> subprocess.Popen:
    stdout_handle = stdout_log.open("w", encoding="utf-8")
    stderr_handle = stderr_log.open("w", encoding="utf-8")
    try:
        try:
            return subprocess.Popen(
                [str(python), str(script)],
                cwd=str(repo_root),
                stdout=stdout_handle,
                stderr=stderr_handle,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess_creation_flags(),
                env=env,
            )
        except PermissionError:
            stdout_handle.close()
            stderr_handle.close()
            stdout_handle = stdout_log.open("a", encoding="utf-8")
            stderr_handle = stderr_log.open("a", encoding="utf-8")
            return subprocess.Popen(
                [str(python), str(script)],
                cwd=str(repo_root),
                stdout=stdout_handle,
                stderr=stderr_handle,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                env=env,
            )
    except Exception:
        stdout_handle.close()
        stderr_handle.close()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Restart nbrag MCP HTTP service.")
    parser.add_argument("--python", default=DEFAULT_PYTHON, help="Python interpreter path")
    parser.add_argument("--script", default=DEFAULT_SCRIPT, help="nbrag MCP startup script")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port")
    parser.add_argument("--ready-timeout", type=float, default=30, help="Seconds to wait for port readiness")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without stopping or starting processes")
    parser.add_argument("--force-port-owner", action="store_true", help="Stop unrelated process owning the target port")
    args = parser.parse_args()

    python = existing_file(args.python, "Python interpreter")
    script = existing_file(args.script, "nbrag MCP startup script")
    repo_root = script.parent.parent
    log_dir = repo_root / "tmp" / "nbrag-mcp-logs"

    print("Restart target:")
    print(f"  Python: {python}")
    print(f"  Script: {script}")
    print(f"  Port:   {args.port}")

    processes = list_processes()
    script_key = norm(str(script))
    targets: dict[int, str] = {
        pid: "command line matches start_http_rag_mcp.py"
        for pid, cmd in processes.items()
        if script_key in norm(cmd) or "start_http_rag_mcp.py" in norm(cmd)
    }

    listeners = port_listener_pids(args.port)
    if listeners:
        print(f"Port {args.port} listener PID(s): {', '.join(map(str, sorted(listeners)))}")
    for pid in listeners:
        if pid in targets:
            continue
        cmd = processes.get(pid, "")
        if "start_http_rag_mcp.py" in norm(cmd):
            targets[pid] = f"owns port {args.port} and matches nbrag startup script"
        elif args.force_port_owner:
            targets[pid] = f"owns port {args.port}; --force-port-owner was supplied"
        else:
            print(f"Port {args.port} is owned by unrelated PID {pid}.")
            if cmd:
                print(f"Command line: {cmd}")
            raise SystemExit("Refusing to stop unrelated port owner. Use --force-port-owner only after confirming it is safe.")

    for pid, reason in sorted(targets.items()):
        stop_pid(pid, reason, args.dry_run)

    if args.dry_run:
        print(f"[dry-run] Would start: {python} {script}")
        return 0

    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stdout_log = log_dir / f"nbrag-mcp-{stamp}.out.log"
    stderr_log = log_dir / f"nbrag-mcp-{stamp}.err.log"

    print("Starting nbrag MCP HTTP service...")
    env = os.environ.copy()
    proc = start_server_process(python, script, repo_root, stdout_log, stderr_log, env)

    deadline = time.time() + args.ready_timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"stdout log: {stdout_log}")
            print(f"stderr log: {stderr_log}")
            raise SystemExit(f"nbrag MCP process exited early with code {proc.returncode}.")
        if port_open(args.port):
            print("nbrag MCP HTTP service is listening.")
            print(f"  PID:        {proc.pid}")
            print(f"  URL:        http://127.0.0.1:{args.port}")
            print(f"  stdout log: {stdout_log}")
            print(f"  stderr log: {stderr_log}")
            return 0
        time.sleep(0.5)

    print(f"stdout log: {stdout_log}")
    print(f"stderr log: {stderr_log}")
    raise SystemExit(f"Timed out waiting for port {args.port} after {args.ready_timeout} seconds.")


if __name__ == "__main__":
    raise SystemExit(main())
