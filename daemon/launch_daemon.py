#!/usr/bin/env python3
"""Cross-platform launcher for MoGe GPU Daemon (Windows, Linux, macOS).

Detects the virtual environment, configures environment paths, and launches moge_daemon.py.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def find_python() -> Path:
    # 1. Explicit MOGE_PY environment variable
    env_py = os.environ.get("MOGE_PY", "").strip().strip('"')
    if env_py and Path(env_py).exists():
        return Path(env_py)

    # 2. Local or parent .venv
    venv_candidates = [
        REPO_ROOT / ".venv",
        REPO_ROOT.parent / ".venv",
        REPO_ROOT / "venv",
        REPO_ROOT.parent / "venv",
        Path.home() / ".venv",
        Path.home() / "MoGe" / ".venv",
    ]
    for venv in venv_candidates:
        if sys.platform == "win32":
            py = venv / "Scripts" / "python.exe"
        else:
            py = venv / "bin" / "python"
        if py.exists():
            return py

    # 3. Current active python
    return Path(sys.executable)


def main():
    py = find_python()
    daemon_script = HERE / "moge_daemon.py"
    if not daemon_script.exists():
        print(f"[ERROR] moge_daemon.py not found at {daemon_script}", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    if not any(arg.startswith("--host") for arg in args):
        args += ["--host", "127.0.0.1"]
    if not any(arg.startswith("--port") for arg in args):
        args += ["--port", "8766"]
    if not any(arg.startswith("--preload") for arg in args):
        args += ["--preload", "v3"]

    cmd = [str(py), str(daemon_script)] + args
    print(f"[LAUNCHER] Running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Daemon stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
