import importlib.util
import subprocess
from pathlib import Path


def _load_restart_process_module():
    script = (
        Path(__file__).resolve().parents[1]
        / ".agents"
        / "skills"
        / "restart_process"
        / "scripts"
        / "restart_process.py"
    )
    spec = importlib.util.spec_from_file_location("restart_process", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_windows_creationflags_detach_service_process():
    module = _load_restart_process_module()

    flags = module._popen_creationflags()

    if module.os.name == "nt":
        assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
        assert flags & subprocess.DETACHED_PROCESS
        assert flags & subprocess.CREATE_NO_WINDOW
        assert flags & subprocess.CREATE_BREAKAWAY_FROM_JOB
    else:
        assert flags == 0


def test_windows_creationflags_can_omit_breakaway_for_fallback():
    module = _load_restart_process_module()

    flags = module._popen_creationflags(include_breakaway=False)

    if module.os.name == "nt":
        assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
        assert flags & subprocess.DETACHED_PROCESS
        assert flags & subprocess.CREATE_NO_WINDOW
        assert not flags & subprocess.CREATE_BREAKAWAY_FROM_JOB
    else:
        assert flags == 0


def test_start_process_uses_detached_creationflags(monkeypatch):
    module = _load_restart_process_module()
    log_dir = Path(__file__).resolve().parents[1] / "tmp" / "pytest-restart-process"
    log_dir.mkdir(parents=True, exist_ok=True)
    calls = {}

    class DummyProcess:
        pid = 12345

    def fake_popen(cmd, cwd, stdout, stderr, creationflags):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        calls["creationflags"] = creationflags
        calls["stdout_closed_at_call"] = stdout.closed
        calls["stderr_closed_at_call"] = stderr.closed
        return DummyProcess()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    pid, out_log, err_log = module.start_process(
        "python.exe",
        "D:/codes/nbrag/scripts/start_http_rag_mcp.py",
        [],
        "D:/codes/nbrag",
        log_dir,
    )

    assert pid == 12345
    assert calls["cmd"] == [
        "python.exe",
        "D:/codes/nbrag/scripts/start_http_rag_mcp.py",
    ]
    assert calls["cwd"] == "D:/codes/nbrag"
    assert calls["creationflags"] == module._popen_creationflags()
    assert calls["stdout_closed_at_call"] is False
    assert calls["stderr_closed_at_call"] is False
    assert out_log is not None
    assert err_log is not None


def test_start_process_falls_back_when_breakaway_is_denied(monkeypatch):
    module = _load_restart_process_module()
    log_dir = Path(__file__).resolve().parents[1] / "tmp" / "pytest-restart-process"
    log_dir.mkdir(parents=True, exist_ok=True)
    creationflags_seen = []

    class DummyProcess:
        pid = 12345

    def fake_popen(cmd, cwd, stdout, stderr, creationflags):
        creationflags_seen.append(creationflags)
        if module.os.name == "nt" and creationflags & subprocess.CREATE_BREAKAWAY_FROM_JOB:
            raise PermissionError(5, "Access is denied")
        return DummyProcess()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    pid, _, _ = module.start_process(
        "python.exe",
        "D:/codes/nbrag/scripts/start_http_rag_mcp.py",
        [],
        "D:/codes/nbrag",
        log_dir,
    )

    assert pid == 12345
    if module.os.name == "nt":
        assert creationflags_seen == [
            module._popen_creationflags(),
            module._popen_creationflags(include_breakaway=False),
        ]
    else:
        assert creationflags_seen == [0]
