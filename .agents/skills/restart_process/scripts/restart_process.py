#!/usr/bin/env python
"""通用进程重启工具：按脚本绝对路径匹配并杀掉进程（含子进程），然后用指定解释器重启。

匹配逻辑：遍历所有进程，把 cmdline 里的脚本参数结合 cwd 解析成绝对路径，
与目标路径比较（大小写+斜杠归一化）。能匹配三种启动方式：
  - python mainxx.py        (cwd=proj1)
  - python proj1/mainxx.py  (cwd=proj1父目录)
  - python D:/codes/proj1/mainxx.py (cwd=任意)

用法:
  python restart_process.py <script_path> --python <python_exe> [options]

示例:
  # 重启 nbrag mcp
  python restart_process.py D:/codes/nbrag/scripts/start_http_rag_mcp.py \
      --python D:/ProgramData/miniconda3/envs/py312/python.exe

  # dry-run（只看不杀）
  python restart_process.py D:/codes/proj1/main.py \
      --python python --args "--port 8000" --dry-run

  # 重启并等待端口
  python restart_process.py D:/codes/proj1/main.py \
      --python python --wait-port 8000 --cwd D:/codes/proj1
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. pip install psutil", file=sys.stderr)
    sys.exit(2)


# ─── 路径归一化 ──────────────────────────────────────────────

def norm_path(p: str) -> str:
    """归一化路径：绝对化 + 统一斜杠 + 小写（Windows 大小写不敏感）。"""
    return os.path.normpath(os.path.abspath(p)).replace("\\", "/").lower()


# ─── 从 cmdline 提取脚本路径 ─────────────────────────────────

def extract_script_from_cmdline(cmdline: list[str], cwd: str | None) -> str | None:
    """从进程 cmdline 里找到脚本参数，结合 cwd 解析成绝对路径。

    Python 规则：第一个非选项参数就是脚本。
    跳过 -m（模块模式）和 -c（代码模式），这两种不是文件路径。
    """
    if not cmdline or len(cmdline) < 2:
        return None
    args = cmdline[1:]  # 去掉解释器本身
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-m", "-c"):
            return None  # 模块/代码模式，不是脚本文件
        if a.startswith("-"):
            i += 1
            continue
        # 第一个非选项参数 = 脚本
        base = cwd or os.getcwd()
        return norm_path(os.path.join(base, a))
    return None


# ─── 查找匹配进程 ────────────────────────────────────────────

def find_matching_processes(target_script: str) -> list[psutil.Process]:
    """找到所有正在运行 target_script 的进程（含主进程，不含子进程）。"""
    target = norm_path(target_script)
    matched: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.cmdline()
            cwd = proc.cwd()
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        if not cmdline:
            continue
        resolved = extract_script_from_cmdline(cmdline, cwd)
        if resolved is None:
            continue
        if resolved == target:
            matched.append(proc)
    return matched


def collect_with_children(procs: list[psutil.Process]) -> list[psutil.Process]:
    """收集主进程 + 所有子进程（递归），去重。"""
    seen: set[int] = set()
    result: list[psutil.Process] = []
    queue = list(procs)
    while queue:
        p = queue.pop()
        try:
            if p.pid in seen or not p.is_running():
                continue
            seen.add(p.pid)
            result.append(p)
            for child in p.children(recursive=True):
                if child.pid not in seen:
                    queue.append(child)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


# ─── 杀进程 ──────────────────────────────────────────────────

def kill_processes(procs: list[psutil.Process], timeout: float = 10.0) -> None:
    """先 terminate（SIGTERM），超时后 kill（SIGKILL）。"""
    # 先对所有进程发 terminate
    for p in procs:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    # 等待退出
    gone, alive = psutil.wait_procs(procs, timeout=timeout)
    # 还活着的强杀
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    psutil.wait_procs(alive, timeout=3)


# ─── 重启 ────────────────────────────────────────────────────

def _popen_creationflags(include_breakaway: bool = True) -> int:
    """Return platform-specific flags for long-running background services."""
    if os.name != "nt":
        return 0
    flags = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    if include_breakaway:
        flags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    return flags


def _popen_with_detach_fallback(cmd, cwd, stdout_fh, stderr_fh):
    """Start process detached; fall back if the parent job forbids breakaway."""
    flags = _popen_creationflags()
    try:
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=stdout_fh,
            stderr=stderr_fh,
            creationflags=flags,
        )
    except PermissionError:
        if os.name != "nt" or not (flags & getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)):
            raise
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=stdout_fh,
            stderr=stderr_fh,
            creationflags=_popen_creationflags(include_breakaway=False),
        )


def start_process(
    python_exe: str,
    script_path: str,
    extra_args: list[str],
    cwd: str | None,
    log_dir: Path | None = None,
) -> tuple[int, Path | None, Path | None]:
    """启动新进程，返回 (pid, stdout_log, stderr_log)。"""
    cmd = [python_exe, script_path] + extra_args
    stdout_file = stderr_file = None
    stdout_fh = stderr_fh = None

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        stem = Path(script_path).stem
        stdout_file = log_dir / f"{stem}_{ts}_stdout.log"
        stderr_file = log_dir / f"{stem}_{ts}_stderr.log"
        stdout_fh = open(stdout_file, "w", encoding="utf-8")
        stderr_fh = open(stderr_file, "w", encoding="utf-8")

    # Windows 上优先按 nohup 类似语义启动；若当前 Job 禁止 breakaway，则降级启动。
    proc = _popen_with_detach_fallback(cmd, cwd, stdout_fh, stderr_fh)
    if stdout_fh:
        stdout_fh.close()
    if stderr_fh:
        stderr_fh.close()
    return proc.pid, stdout_file, stderr_file


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 30.0) -> bool:
    """轮询等待端口可连。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (OSError, socket.timeout):
            time.sleep(0.5)
    return False


# ─── 主流程 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="按脚本绝对路径重启进程（杀旧+启新），支持任意启动目录。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "script_path",
        help="目标脚本的绝对路径，例如 D:/codes/nbrag/scripts/start_http_rag_mcp.py",
    )
    parser.add_argument(
        "--python",
        required=True,
        help="重启时使用的 Python 解释器路径，例如 D:/ProgramData/miniconda3/envs/py312/python.exe",
    )
    parser.add_argument(
        "--args",
        default="",
        help="重启时传给脚本的额外参数（空格分隔），例如 '--port 9101 --verbose'",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="重启时的工作目录，默认为脚本所在目录",
    )
    parser.add_argument(
        "--wait-port",
        type=int,
        default=None,
        help="重启后等待此端口可连才判定成功（可选）",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="日志输出目录，默认 tmp/restart-logs/（相对于脚本运行位置）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只展示会杀哪些进程，不实际杀/启动",
    )
    parser.add_argument(
        "--kill-only",
        action="store_true",
        help="只杀不重启",
    )
    args = parser.parse_args()

    # 校验脚本路径
    script_abs = Path(args.script_path).resolve()
    if not script_abs.is_file():
        print(f"ERROR: script not found: {args.script_path}", file=sys.stderr)
        sys.exit(2)

    target_script = str(script_abs)
    print(f"[target] {target_script}")

    # 校验 python 解释器
    python_abs = Path(args.python)
    if not python_abs.is_file() and args.python != sys.executable:
        # 允许 "python" 这种 PATH 查找，但提示
        pass

    # 设置默认 cwd
    cwd = args.cwd or str(script_abs.parent)

    # 设置日志目录
    if args.log_dir:
        log_dir = Path(args.log_dir)
    else:
        log_dir = Path("tmp/restart-logs")

    extra_args = args.args.split() if args.args else []

    # ── Step 1: 查找匹配进程 ──
    matched = find_matching_processes(target_script)
    if matched:
        print(f"\n[found] {len(matched)} process(es) running this script:")
        for p in matched:
            try:
                cmdline = " ".join(p.cmdline())
                pcwd = p.cwd()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                cmdline = "?"
                pcwd = "?"
            print(f"  PID={p.pid}  cwd={pcwd}")
            print(f"    cmdline: {cmdline}")
    else:
        print("\n[found] 0 processes running this script (nothing to kill)")

    # ── Step 2: 收集子进程 ──
    if matched:
        with_children = collect_with_children(matched)
        child_count = len(with_children) - len(matched)
        if child_count > 0:
            print(f"[children] +{child_count} child process(es)")
            for p in with_children:
                if p not in matched:
                    try:
                        print(f"  PID={p.pid}  cmdline: {' '.join(p.cmdline())}")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        print(f"  PID={p.pid}  (info unavailable)")
    else:
        with_children = []

    # ── Step 3: dry-run 截止 ──
    if args.dry_run:
        print("\n[dry-run] 不执行 kill / restart")
        if not args.kill_only:
            print(f"[would-start] {args.python} {target_script} {' '.join(extra_args)}")
            print(f"  cwd={cwd}")
        return

    # ── Step 4: 杀进程 ──
    if with_children:
        print(f"\n[kill] terminating {len(with_children)} process(es)...")
        kill_processes(with_children)
        print("[kill] done")

    # ── Step 5: 重启 ──
    if args.kill_only:
        print("\n[kill-only] 不重启")
        return

    print(f"\n[start] {args.python} {target_script} {' '.join(extra_args)}")
    print(f"  cwd={cwd}")
    pid, out_log, err_log = start_process(
        args.python, target_script, extra_args, cwd, log_dir
    )
    print(f"[start] new PID={pid}")
    if out_log:
        print(f"  stdout: {out_log}")
    if err_log:
        print(f"  stderr: {err_log}")

    # ── Step 6: 等待端口 ──
    if args.wait_port:
        print(f"\n[wait] port {args.wait_port} ...")
        if wait_for_port(args.wait_port):
            print(f"[wait] port {args.wait_port} is open ✓")
        else:
            print(f"[wait] port {args.wait_port} timeout ✗", file=sys.stderr)
            if err_log:
                print(f"  check stderr: {err_log}", file=sys.stderr)
            sys.exit(1)

    print("\n[done]")


if __name__ == "__main__":
    main()
