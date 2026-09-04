"""HTTP networking and daemon process lifecycle for MoGe Splat Studio."""
from __future__ import annotations

import os
import io
import sys
import json
import uuid
import tempfile
import http.client
import subprocess
from pathlib import Path

import bpy

from .preferences import get_preferences


def get_daemon_endpoint() -> tuple[str, int]:
    """Retrieve host and port from AddonPreferences or environment."""
    prefs = get_preferences()
    host = os.environ.get("MOGE_DAEMON_HOST")
    if not host and prefs:
        host = prefs.daemon_host
    host = host or "127.0.0.1"

    port_env = os.environ.get("MOGE_DAEMON_PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            port = 8766
    elif prefs:
        port = prefs.daemon_port
    else:
        port = 8766

    return host, port


def daemon_get(path: str, timeout: float = 3.0):
    host, port = get_daemon_endpoint()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, data
    finally:
        conn.close()


def daemon_post_multipart(
    path: str,
    fields: dict,
    file_field: str,
    filename: str,
    file_bytes: bytes,
    file_mime: str = "image/jpeg",
    timeout: float = 120.0,
    extra_files=None,
):
    host, port = get_daemon_endpoint()
    boundary = f"----MoGe{uuid.uuid4().hex}"
    body = io.BytesIO()

    def _part(field, fname, fbytes, fmime):
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{field}"; filename="{fname}"\r\n'.encode())
        body.write(f"Content-Type: {fmime}\r\n\r\n".encode())
        body.write(fbytes)
        body.write(b"\r\n")

    for k, v in fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.write(f"{v}\r\n".encode())

    _part(file_field, filename, file_bytes, file_mime)
    for ef, en, eb, em in (extra_files or []):
        _part(ef, en, eb, em)
    body.write(f"--{boundary}--\r\n".encode())
    payload = body.getvalue()

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload)),
    }
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("POST", path, body=payload, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        ctype = resp.getheader("Content-Type", "")
        return resp.status, ctype, data
    finally:
        conn.close()


def _daemon_log_path() -> Path:
    return Path(tempfile.gettempdir()) / "moge_daemon.log"


def _daemon_pid_path() -> Path:
    return Path(tempfile.gettempdir()) / "moge_daemon.pid"


def _find_daemon_script() -> Path:
    """Find daemon/moge_daemon.py dynamically."""
    env = os.environ.get("MOGE_HOME", "").strip().strip('"')
    if env and (Path(env) / "daemon" / "moge_daemon.py").exists():
        return Path(env) / "daemon" / "moge_daemon.py"

    # Search from this file's repo root
    here = Path(__file__).resolve()
    for parent in (here,) + tuple(here.parents):
        cand = parent / "daemon" / "moge_daemon.py"
        if cand.exists():
            return cand
        cand_sub = parent / "moge_daemon.py"
        if cand_sub.exists():
            return cand_sub

    # Current working directory checkouts
    for cand in [Path.cwd() / "daemon" / "moge_daemon.py", Path.cwd() / "moge_daemon.py"]:
        if cand.exists():
            return cand

    raise FileNotFoundError("Could not locate moge_daemon.py. Please set MOGE_HOME environment variable.")


def resolve_daemon_python(props=None) -> Path:
    """Find Python with PyTorch and MoGe installed."""
    # 1. Check Scene Property override
    if props is not None:
        custom = (getattr(props, "daemon_python", "") or "").strip().strip('"')
        if custom and Path(custom).exists():
            return Path(custom)

    # 2. Check Addon Preferences
    prefs = get_preferences()
    if prefs and prefs.daemon_python:
        p = Path(prefs.daemon_python.strip().strip('"'))
        if p.exists():
            return p

    # 3. Check MOGE_PY environment variable
    env = os.environ.get("MOGE_PY", "").strip().strip('"')
    if env and Path(env).exists():
        return Path(env)

    # 4. Search local repo .venv and user workspaces
    try:
        daemon_script = _find_daemon_script()
        repo_root = daemon_script.parent.parent
        user_docs = Path.home() / "Documents"
        venv_candidates = [
            repo_root / ".venv",
            repo_root.parent / ".venv",
            repo_root.parent / "MoGe" / ".venv",
            Path.home() / ".venv",
            Path.home() / "MoGe" / ".venv",
            user_docs / "antigravity" / "mysterious-archimedes" / "MoGe" / ".venv",
            user_docs / "MoGe" / ".venv",
        ]
        for venv in venv_candidates:
            if sys.platform == "win32":
                py = venv / "Scripts" / "python.exe"
            else:
                py = venv / "bin" / "python"
            if py.exists():
                return py
    except Exception:
        pass

    # Never silently fall back to Blender's bundled Python (it lacks PyTorch/cv2)
    raise FileNotFoundError(
        "Could not automatically locate a Python environment with PyTorch and MoGe. "
        "Please set your Python path in MoGe Addon Preferences (e.g. your MoGe .venv/Scripts/python.exe)."
    )


def daemon_health() -> tuple[str, any]:
    """Classify daemon state: ('ok', dict), ('refused', str), ('conflict', str), ('error', str)."""
    try:
        status, data = daemon_get("/health", timeout=2.5)
    except (ConnectionRefusedError, OSError) as e:
        return "refused", f"{type(e).__name__}: {e}"
    except Exception as e:
        return "error", f"{type(e).__name__}: {e}"

    if status == 200:
        try:
            return "ok", json.loads(data.decode("utf-8", "replace"))
        except Exception as e:
            return "error", f"bad /health payload: {e}"
    host, port = get_daemon_endpoint()
    if status == 404:
        return "conflict", f"HTTP 404 on :{port} (foreign server listening)"
    return "error", f"HTTP {status}: {data[:200]!r}"


def daemon_start(py: Path) -> int:
    """Spawn daemon as detached background process."""
    script = _find_daemon_script()
    host, port = get_daemon_endpoint()

    log_path = _daemon_log_path()
    log_f = open(log_path, "ab")
    cmd = [str(py), str(script), "--host", host, "--port", str(port), "--preload", "v3"]

    kwargs = {
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
        "cwd": str(script.parent),
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    try:
        _daemon_pid_path().write_text(str(proc.pid))
    except Exception:
        pass
    return proc.pid


def daemon_stop() -> tuple[bool, str]:
    """Terminate the daemon process if running."""
    pid_file = _daemon_pid_path()
    if not pid_file.exists():
        return False, "No running daemon PID file found."

    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return False, "Invalid PID file."

    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        return True, f"Stopped daemon (PID {pid})."
    except Exception as e:
        pid_file.unlink(missing_ok=True)
        return False, f"Could not stop PID {pid}: {e}"


def _is_pid_running(pid: int) -> bool:
    """Check if process with given PID is currently active."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _read_log_tail(n_lines: int = 10) -> str:
    """Read last N lines from daemon log."""
    log_p = _daemon_log_path()
    if not log_p.exists():
        return ""
    try:
        lines = log_p.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n_lines:])
    except Exception:
        return ""


def ensure_daemon_ready(props=None, autostart: bool = True) -> tuple[bool, str]:
    """Ensure daemon is up and responsive."""
    state, payload = daemon_health()
    if state == "ok":
        models = ",".join(payload.get("models_loaded", [])) or "ready"
        return True, f"Daemon ready (model: {models})"
    if state == "conflict":
        host, port = get_daemon_endpoint()
        return False, f"Port {port} conflict: {payload}"
    if state == "error":
        return False, f"Daemon error: {payload}"

    if not autostart:
        host, port = get_daemon_endpoint()
        return False, f"Daemon not running on :{port}. Please start it or enable auto-start."

    try:
        py = resolve_daemon_python(props)
        pid = daemon_start(py)
    except Exception as e:
        return False, f"Auto-start failed: {e}"

    # Poll until ready
    import time
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 60.0:
        st, p = daemon_health()
        if st == "ok":
            return True, f"Daemon auto-started (PID {pid}) in {time.perf_counter() - t0:.1f}s"
        if st == "conflict":
            return False, f"Conflict: {p}"

        # Fast-fail if process died during startup
        if not _is_pid_running(pid):
            log_tail = _read_log_tail(8)
            msg = f"Daemon process (PID {pid}) crashed during startup."
            if log_tail:
                msg += f"\n{log_tail}"
            return False, msg

        time.sleep(1.0)

    return False, f"Daemon started (PID {pid}) but timed out waiting for /health."
