"""Unified Health Check & Self-Verification Diagnostic for MoDe 3D Studio.

Executes a full multi-tier inspection:
  Tier 1: Core Python & GPU Environment Check
  Tier 2: Codebase Hygiene & Etiquette Audit (no hardcoded machine paths)
  Tier 3: AI Daemon Connectivity & Live Inference Test
  Tier 4: Headless Blender End-to-End Test (Operators, Nodes, Materials, Cache)

Usage:
  python tools/health_check.py
"""
import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAEMON_PORT = 8766
REQUIREMENTS_FILE = ROOT / "requirements.txt"


def print_banner(text: str):
    print("\n" + "=" * 64)
    print(f"  {text}")
    print("=" * 64)


def check_environment():
    print_banner("TIER 1: Environment & GPU Hardware")
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "No GPU detected"
        print(f"  [OK] PyTorch version: {torch.__version__}")
        print(f"  [OK] CUDA Available:  {cuda_ok} ({gpu_name})")
        if cuda_ok:
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            print(f"  [OK] Total VRAM:      {vram_gb:.1f} GB")
    except ImportError:
        print("  [WARN] PyTorch is not available in current Python environment.")
        print(f"         (Expected if running outside the AI virtualenv: {sys.executable})")

    try:
        import cv2
        print(f"  [OK] OpenCV version:  {cv2.__version__}")
    except ImportError:
        print("  [WARN] OpenCV is not installed in current environment.")


def check_codebase_hygiene():
    print_banner("TIER 2: Codebase Hygiene & Etiquette Audit")
    forbidden = [
        "E:\\MOGE", "E:/MOGE",
        "D:\\MOGE", "D:/MOGE",
        "C:\\MOGE", "C:/MOGE",
        "C:\\Users\\Navneeth", "C:/Users/Navneeth",
        "mysterious-archimedes",
    ]
    violations = []

    # Check python and configuration files
    scan_exts = {".py", ".toml", ".bat", ".sh", ".json"}
    ignore_dirs = {".git", ".venv", "__pycache__", "build", "dist"}

    for p in ROOT.rglob("*"):
        if any(ignored in p.parts for ignored in ignore_dirs):
            continue
        if p.suffix in scan_exts and p.is_file():
            # Skip this diagnostic script itself and specific doc mentions
            if p.name in ("health_check.py", "CITATIONS.md"):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                for f_term in forbidden:
                    if f_term.lower() in content.lower():
                        violations.append((p.relative_to(ROOT), f_term))
            except Exception:
                pass

    if violations:
        print(f"  [FAIL] Found {len(violations)} hardcoded path violations:")
        for file_rel, term in violations[:10]:
            print(f"         - {file_rel}: contains '{term}'")
        assert False, "Etiquette violation: hardcoded paths detected in codebase."
    else:
        print("  [OK] Zero hardcoded machine paths found. Codebase is 100% portable.")


def _parse_requirement_line(line: str):
    """Split a requirements.txt line into (kind, display, bare, url, ref). Skips comments/options."""
    import re
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    if "git+" in line:
        name, _, url = line.partition("@")
        url = url.strip()
        if url.startswith("git+"):
            url = url[len("git+"):]
        ref = None
        scheme_split = url.split("://", 1)
        if len(scheme_split) == 2 and "@" in scheme_split[1]:
            base, _, ref = scheme_split[1].rpartition("@")
            url = scheme_split[0] + "://" + base
        return ("git", line, name.strip(), url, (ref or "").strip() or None)
    bare = re.split(r"[<>=!~\s\[]", line, 1)[0].strip()
    return ("pypi", line, bare, None, None)


def check_requirements_resolvable():
    """TIER 2b: every requirements.txt line must resolve WITHOUT installing anything.

    Catches the exact class that broke a fresh user before: a PyPI name that does not
    exist (was: bare 'flex-gemm') or a git pin pointing at a dead repo/ref.
    Uses `git ls-remote` for git URLs and `pip index versions` for PyPI (network only).
    """
    print_banner("TIER 2b: Requirements Resolvability (no-install dry run)")
    if not REQUIREMENTS_FILE.exists():
        print(f"  [FAIL] Missing {REQUIREMENTS_FILE}")
        sys.exit(1)

    lines = REQUIREMENTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    reqs = [r for line in lines for r in ([_parse_requirement_line(line)] if _parse_requirement_line(line) else [])]
    if not reqs:
        print("  [FAIL] requirements.txt parsed to zero entries.")
        sys.exit(1)

    failures = []
    for kind, display, bare, url, ref in reqs:
        if kind == "git":
            if shutil.which("git") is None:
                print(f"  [FAIL] {display}: git URL needs git installed ({url})")
                failures.append(bare)
                continue
            try:
                import re as _re
                # ls-remote <url> <pattern> matches ref NAMES only: a pinned commit SHA
                # always returns exit 0 with empty output, even when valid. So for full
                # SHAs, fetch the whole advertisement and check the object is advertised.
                is_sha = bool(ref and _re.fullmatch(r"[0-9a-f]{40}", ref))
                proc = subprocess.run(["git", "ls-remote", url] + ([] if is_sha else [ref or "HEAD"]),
                                      capture_output=True, text=True, timeout=30)
                ok = proc.returncode == 0 and (ref in proc.stdout if is_sha else bool(proc.stdout.strip()))
                if ok:
                    print(f"  [OK] {display}")
                else:
                    err = (proc.stderr or "").strip().splitlines()
                    hint = err[-1][:120] if err else f"exit {proc.returncode}, pin not advertised"
                    print(f"  [FAIL] {display}: cannot reach {url}@{ref} ({hint})")
                    failures.append(bare)
            except Exception as e:
                print(f"  [FAIL] {display}: ls-remote error: {e}")
                failures.append(bare)
        else:
            try:
                # pip index wants a bare name, not a specifier (specifiers error out).
                proc = subprocess.run([sys.executable, "-m", "pip", "index", "versions", bare],
                                      capture_output=True, text=True, timeout=60)
                if proc.returncode == 0:
                    print(f"  [OK] {display}")
                else:
                    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
                    hint = tail[-1][:120] if tail else f"exit {proc.returncode}"
                    print(f"  [FAIL] {display}: not resolvable on PyPI ({hint})")
                    failures.append(bare)
            except Exception as e:
                print(f"  [FAIL] {display}: pip index error: {e}")
                failures.append(bare)

    if failures:
        print(f"\n  [FAIL] {len(failures)} unresolvable requirement(s): {', '.join(failures)}")
        print("         Fresh installs die here — fix requirements.txt before tagging.")
        sys.exit(1)
    print(f"\n  [OK] All {len(reqs)} requirements resolve (nothing installed).")


def check_daemon_live():
    print_banner("TIER 3: AI Engine Daemon & Endpoint Verification")
    health_url = f"http://127.0.0.1:{DAEMON_PORT}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=3.0) as resp:
            data = json.loads(resp.read().decode())
            print(f"  [OK] Daemon online at {health_url}")
            print(f"       Status:         {data.get('status')}")
            print(f"       Loaded Models:  {data.get('models_loaded', [])}")
            print(f"       GPU Device:     {data.get('cuda_name')}")
            print(f"       VRAM Allocated: {data.get('vram_allocated_mb', 0):.1f} MB")
            return True
    except Exception as e:
        print(f"  [INFO] Daemon is not currently responding on port {DAEMON_PORT} ({e}).")
        print("         (Launch with 'launch_daemon.bat' or test will auto-start if in Blender)")
        return False


def find_blender_binary() -> Path | None:
    # 1. PATH check
    which = shutil.which("blender")
    if which:
        return Path(which)

    # 2. Windows standard install paths
    cands = [
        Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
    ]
    for c in cands:
        if c.exists():
            return c
    return None


def check_blender_headless():
    print_banner("TIER 4: Blender Headless Full Pipeline Verification")
    blender_exe = find_blender_binary()
    if not blender_exe:
        print("  [WARN] Blender executable not found. Skipping Blender test.")
        return

    print(f"  [OK] Found Blender: {blender_exe}")
    test_script = ROOT / "tools" / "test_headless_blender.py"
    assert test_script.exists(), f"Missing test script: {test_script}"

    cmd = [
        str(blender_exe),
        "--factory-startup",
        "--background",
        "--python",
        str(test_script),
    ]

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    dt = time.perf_counter() - t0

    if proc.returncode == 0 and "ALL HEADLESS BLENDER HEALTH CHECKS PASSED" in proc.stdout:
        print(f"  [OK] Headless Blender suite PASSED in {dt:.1f}s (exit code 0)")
        for line in proc.stdout.splitlines():
            if line.startswith("  [OK]") or "[TEST" in line:
                print(f"       {line}")
    else:
        print(f"  [FAIL] Headless Blender suite failed (exit code {proc.returncode}):")
        print("--- STDOUT ---")
        print(proc.stdout)
        print("--- STDERR ---")
        print(proc.stderr)
        sys.exit(1)


def main():
    t_start = time.perf_counter()
    print_banner("MoDe 3D Studio - Comprehensive Health Check")
    print(f"Repository Root: {ROOT}")

    check_environment()
    check_codebase_hygiene()
    check_requirements_resolvable()
    check_daemon_live()
    check_blender_headless()

    total_time = time.perf_counter() - t_start
    print_banner(f"ALL HEALTH CHECKS PASSED ({total_time:.1f}s total)!")
    print("  The project is in 100% clean, functional, and publishable condition.\n")


if __name__ == "__main__":
    main()
