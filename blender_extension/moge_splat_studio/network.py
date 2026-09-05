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

try:
    import bpy
    from .preferences import get_preferences
except Exception:
    bpy = None

    def get_preferences(context=None):
        return None


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


def _get_cache_root_safe() -> Path:
    try:
        from .cleanup import get_cache_root
        return get_cache_root()
    except Exception:
        pass
    try:
        from cleanup import get_cache_root
        return get_cache_root()
    except Exception:
        pass
    p = Path(tempfile.gettempdir()) / "moge_splat_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _daemon_log_path() -> Path:
    return _get_cache_root_safe() / "moge_daemon.log"


def _daemon_pid_path() -> Path:
    return _get_cache_root_safe() / "moge_daemon.pid"


def get_global_config_path() -> Path:
    """Return user-level persistent config path."""
    return Path.home() / ".mode_3d" / "config.json"


def read_saved_config() -> dict:
    """Read machine-specific paths saved by the one-click installer."""
    # 1. Check staged config in this extension's folder
    try:
        local_cfg = Path(__file__).resolve().parent / "mode_3d_config.json"
        if local_cfg.exists():
            with open(local_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass

    # 2. Check global user profile (~/.mode_3d/config.json)
    try:
        global_cfg = get_global_config_path()
        if global_cfg.exists():
            with open(global_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass

    return {}


def _find_daemon_script() -> Path:
    """Find daemon/moge_daemon.py dynamically."""
    # 1. Environment variable
    env = os.environ.get("MOGE_HOME", "").strip().strip('"')
    if env:
        for sub in ("daemon/moge_daemon.py", "moge_daemon.py"):
            c = Path(env) / sub
            if c.exists():
                return c

    # 2. Check saved persistent config
    cfg = read_saved_config()
    cfg_script = cfg.get("daemon_script")
    if cfg_script and Path(cfg_script).exists():
        return Path(cfg_script)

    cfg_root = cfg.get("repo_root")
    if cfg_root:
        for sub in ("daemon/moge_daemon.py", "moge_daemon.py"):
            c = Path(cfg_root) / sub
            if c.exists():
                return c

    # 3. Search upward from this file's repo root
    here = Path(__file__).resolve()
    for parent in (here,) + tuple(here.parents):
        cand = parent / "daemon" / "moge_daemon.py"
        if cand.exists():
            return cand
        cand_sub = parent / "moge_daemon.py"
        if cand_sub.exists():
            return cand_sub

    # 4. Search common workspace paths and current working directory
    user_docs = Path.home() / "Documents"
    candidate_dirs = [
        Path.cwd(),
        Path.cwd() / "daemon",
        Path.home() / "mode-3d",
        Path.home() / "MoGe",
        user_docs / "mode-3d",
        user_docs / "MoGe",
    ]
    for d in candidate_dirs:
        for script_name in ("daemon/moge_daemon.py", "moge_daemon.py"):
            c = d / script_name
            if c.exists():
                return c

    raise FileNotFoundError(
        "Could not locate 'moge_daemon.py'. "
        "Please run 'Start_MoDe_3D.bat' in your downloaded MoDe 3D folder once to register the engine."
    )


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

    # 4. Check saved persistent config from one-click setup
    cfg = read_saved_config()
    cfg_py = cfg.get("python_bin")
    if cfg_py and Path(cfg_py).exists():
        return Path(cfg_py)

    cfg_root = cfg.get("repo_root")
    if cfg_root:
        if sys.platform == "win32":
            cand_py = Path(cfg_root) / ".venv" / "Scripts" / "python.exe"
        else:
            cand_py = Path(cfg_root) / ".venv" / "bin" / "python"
        if cand_py.exists():
            return cand_py

    # 5. Search local repo .venv and user workspaces (decoupled from _find_daemon_script)
    venv_candidates = []
    try:
        daemon_script = _find_daemon_script()
        repo_root = daemon_script.parent.parent
        venv_candidates.extend([
            repo_root / ".venv",
            repo_root.parent / ".venv",
            repo_root.parent / "MoGe" / ".venv",
        ])
    except Exception:
        pass

    user_docs = Path.home() / "Documents"
    venv_candidates.extend([
        Path.home() / ".venv",
        Path.home() / "mode-3d" / ".venv",
        Path.home() / "MoGe" / ".venv",
        user_docs / "mode-3d" / ".venv",
        user_docs / "MoGe" / ".venv",
    ])

    for venv in venv_candidates:
        if sys.platform == "win32":
            py = venv / "Scripts" / "python.exe"
        else:
            py = venv / "bin" / "python"
        if py.exists():
            return py

    # Never silently fall back to Blender's bundled Python (it lacks PyTorch/cv2)
    raise FileNotFoundError(
        "MoDe 3D AI Engine is not configured.\n"
        "Please run 'Start_MoDe_3D.bat' in your downloaded MoDe 3D folder once to set up the engine automatically, "
        "or set your Python path in Addon Preferences."
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


def daemon_start(py: Path, variant: str = "vitl") -> int:
    """Spawn daemon as detached background process."""
    script = _find_daemon_script()
    host, port = get_daemon_endpoint()

    log_path = _daemon_log_path()
    cmd = [
        str(py), str(script),
        "--host", host,
        "--port", str(port),
        "--preload", "v3",
        "--variant", str(variant or "vitl"),
    ]

    log_f = open(log_path, "ab")
    try:
        kwargs = {
            "stdout": log_f,
            "stderr": subprocess.STDOUT,
            "cwd": str(script.parent),
            "close_fds": True,
        }
        if os.name == "nt":
            # DETACHED_PROCESS (0x08) | CREATE_NEW_PROCESS_GROUP (0x200) | CREATE_NO_WINDOW (0x08000000)
            kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)
    finally:
        log_f.close()

    try:
        _daemon_pid_path().write_text(str(proc.pid))
    except Exception:
        pass
    return proc.pid


def _verify_process_is_python(pid: int) -> bool:
    """Verify that a PID belongs to a Python process before killing it."""
    if pid <= 100:  # Protect system/reserved PIDs (0, 4, etc.)
        return False
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = proc.stdout.lower()
            return "python" in out
        else:
            cmdline_file = Path(f"/proc/{pid}/cmdline")
            if cmdline_file.exists():
                cmdline = cmdline_file.read_text(errors="ignore").lower()
                return "python" in cmdline or "moge_daemon" in cmdline
            proc = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True,
                text=True,
                check=False,
            )
            return "python" in proc.stdout.lower()
    except Exception:
        return False


def daemon_stop() -> tuple[bool, str]:
    """Terminate the daemon process if running, with safety checks."""
    pid_file = _daemon_pid_path()
    if not pid_file.exists():
        return False, "No running daemon PID file found."

    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return False, "Invalid PID file."

    if pid <= 100:
        pid_file.unlink(missing_ok=True)
        return False, f"Refusing to kill reserved/system PID {pid}."

    if not _is_pid_running(pid):
        pid_file.unlink(missing_ok=True)
        return True, f"Daemon process (PID {pid}) is not running."

    if not _verify_process_is_python(pid):
        pid_file.unlink(missing_ok=True)
        return False, f"Refusing to kill PID {pid}: process is not Python."

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
        variant = getattr(props, "model_variant", "vitl") if props else "vitl"
        pid = daemon_start(py, variant=variant)
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
