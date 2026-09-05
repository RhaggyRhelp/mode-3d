"""MoDe 3D Studio - One-Click Automated Setup & Launcher.

Ensures the entire environment is ready without manual terminal commands:
1. Verifies Python version (>= 3.10).
2. Sets up or activates the local virtual environment (.venv).
3. Installs PyTorch with CUDA acceleration if not present.
4. Installs requirements from requirements.txt.
5. Clones/links the upstream MoGe repository if needed.
6. Packages and auto-stages the Blender extension into local Blender installations.
7. Launches the warm GPU AI engine daemon with user-friendly instructions.
"""
from __future__ import annotations

import argparse
import os
import sys
import shutil
import venv
import subprocess
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAEMON_SCRIPT = REPO_ROOT / "daemon" / "moge_daemon.py"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
VENV_DIR = REPO_ROOT / ".venv"
DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 8766

MIN_PY = (3, 10)
MAX_PY = (3, 13)  # exclusive upper bound; 3.10–3.12 tested, 3.13 best-effort
MOGE_URL = "https://github.com/microsoft/MoGe.git"
MOGE_REF = "main"  # pin to a tag/commit here once validated, e.g. "v1.0.0"
TORCH_INDEXES = [
    "https://download.pytorch.org/whl/cu128",
    "https://download.pytorch.org/whl/cu121",
]


def check_python_version() -> None:
    vi = sys.version_info
    if vi[:2] < MIN_PY or vi[:2] >= MAX_PY:
        print(f"[ERROR] Python {vi.major}.{vi.minor} detected; MoDe 3D needs "
              f"Python {MIN_PY[0]}.{MIN_PY[1]}–{MAX_PY[0]}.{MAX_PY[1] - 1}. "
              f"Install a supported version from https://www.python.org/downloads/ "
              f"(check 'Add Python to PATH').", file=sys.stderr)
        sys.exit(1)


def daemon_already_running() -> bool:
    import json
    url = f"http://{DAEMON_HOST}:{DAEMON_PORT}/health"
    try:
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            return data.get("status") == "ok"
    except Exception:
        return False


def uninstall_all() -> int:
    print_banner("MoDe 3D Studio - Uninstall")
    removed = 0
    # 1. Staged Blender extension(s)
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        from install_extension import find_blender_extension_dir
        stage = find_blender_extension_dir()
        if stage and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
            print(f"  [OK] Removed staged extension: {stage}")
            removed += 1
        else:
            print("  [INFO] No staged Blender extension found.")
    except Exception as e:
        print(f"  [WARN] Stage removal skipped: {e}")
    finally:
        try:
            sys.path.remove(str(REPO_ROOT / "tools"))
        except ValueError:
            pass
    # 2. Global + local configs
    for cfg in (Path.home() / ".mode_3d" / "config.json",
                REPO_ROOT / "moge_temp.zip"):
        try:
            if cfg.exists():
                cfg.unlink()
                print(f"  [OK] Removed {cfg}")
                removed += 1
        except Exception as e:
            print(f"  [WARN] Could not remove {cfg}: {e}")
    # 3. Desktop shortcut
    try:
        shortcut = Path.home() / "Desktop" / "MoDe 3D Studio.lnk"
        if shortcut.exists():
            shortcut.unlink()
            print(f"  [OK] Removed {shortcut.name}")
            removed += 1
    except Exception as e:
        print(f"  [WARN] Shortcut removal skipped: {e}")
    print(f"\nDone ({removed} items). .venv/ left in place; delete it manually for a full wipe.")
    return 0


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def get_venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def is_running_in_target_venv() -> bool:
    try:
        venv_py = get_venv_python().resolve()
        curr_py = Path(sys.executable).resolve()
        return venv_py == curr_py
    except Exception:
        return False


def ensure_venv():
    if not VENV_DIR.exists():
        print("[SETUP] Creating isolated Python virtual environment (.venv)...")
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(VENV_DIR)
        print("[SETUP] Virtual environment created successfully.")


def run_cmd(args: list[str], desc: str, check: bool = True) -> int:
    print(f"[SETUP] {desc}...")
    proc = subprocess.run(args, cwd=str(REPO_ROOT))
    if check and proc.returncode != 0:
        print(f"[ERROR] Failed during: {desc} (exit code {proc.returncode})", file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.returncode


def check_and_install_dependencies():
    # 0. pip bootstrap (quiet, best-effort)
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "pip"],
                       cwd=str(REPO_ROOT), capture_output=True, check=False)
    except Exception:
        pass
    # 1. Check PyTorch & CUDA
    print("[SETUP] Checking PyTorch and CUDA hardware acceleration...")
    has_torch = False
    has_cuda = False
    try:
        import torch
        has_torch = True
        has_cuda = torch.cuda.is_available()
        print(f"  [OK] PyTorch {torch.__version__} found (CUDA: {has_cuda})")
    except ImportError:
        pass

    if not has_torch or not has_cuda:
        if shutil.which("nvidia-smi") is None and not has_cuda:
            print("  [WARN] No NVIDIA driver (nvidia-smi) detected. CUDA install may still work, "
                  "but the daemon needs an NVIDIA GPU; otherwise use Blender CPU-only tools.")
        installed = False
        for index_url in TORCH_INDEXES:
            print(f"[SETUP] Installing PyTorch (this may take a few minutes on first run) via {index_url} ...")
            cmd = [
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision",
                "--index-url", index_url,
            ]
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
            if proc.returncode == 0:
                installed = True
                break
            print(f"  [WARN] Torch install failed via {index_url} (exit {proc.returncode}); trying fallback...")
        if not installed:
            print("[ERROR] PyTorch CUDA install failed. Install manually from https://pytorch.org/get-started/locally/ "
                  "then re-run setup.", file=sys.stderr)
            sys.exit(1)

    # 2. Check requirements.txt (import name -> pip name for clearer errors)
    print("[SETUP] Verifying daemon requirements (FastAPI, OpenCV, flex-gemm, utils3d)...")
    dep_checks = (
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("multipart", "python-multipart"),
        ("cv2", "opencv-python"),
        ("PIL", "pillow"),
        ("torchvision", "torchvision"),
        ("huggingface_hub", "huggingface-hub"),
        ("scipy", "scipy"),
        ("flex_gemm", "flex-gemm"),
    )
    req_missing = False
    for mod, _pip in dep_checks:
        try:
            __import__(mod)
        except ImportError:
            req_missing = True
            break
    try:
        import utils3d_moge  # noqa: F401
    except ImportError:
        try:
            import utils3d  # noqa: F401
        except ImportError:
            req_missing = True

    if req_missing:
        # requirements.txt installs two deps straight from git (flex-gemm, utils3d_moge),
        # so git must exist before pip runs — otherwise pip dies with a cryptic error.
        if shutil.which("git") is None:
            print("[ERROR] Git is required (two AI packages install directly from GitHub) but was not found.",
                  file=sys.stderr)
            print("        Install it from https://git-scm.com/downloads/win, restart this window,",
                  file=sys.stderr)
            print("        then double-click Start_MoDe_3D.bat again.", file=sys.stderr)
            sys.exit(1)
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)]
        run_cmd(cmd, "Installing requirements.txt packages")
    else:
        print("  [OK] All core dependencies are installed.")

    # 3. Check MoGe upstream repository
    moge_ready = False
    try:
        import moge
        moge_ready = True
    except ImportError:
        pass

    if not moge_ready:
        moge_dir = REPO_ROOT / "MoGe"
        if not moge_dir.exists() or not (moge_dir / "moge").exists():
            print("[SETUP] Downloading upstream MoGe vision backbone from GitHub...")
            git_found = shutil.which("git") is not None
            if git_found:
                run_cmd(["git", "clone", "--depth", "1", "--branch", MOGE_REF,
                         MOGE_URL, str(moge_dir)], "Cloning MoGe repository (shallow)")
            else:
                # Fallback: download zip from GitHub
                print("[SETUP] Git not found. Downloading MoGe zip archive directly...")
                zip_url = "https://github.com/microsoft/MoGe/archive/refs/heads/main.zip"
                tmp_zip = REPO_ROOT / "moge_temp.zip"
                urllib.request.urlretrieve(zip_url, tmp_zip)
                with zipfile.ZipFile(tmp_zip, "r") as z:
                    # Security safeguard: Prevent Zip Slip (path traversal outside REPO_ROOT)
                    resolved_root = REPO_ROOT.resolve()
                    for member in z.infolist():
                        target_p = (REPO_ROOT / member.filename).resolve()
                        if not str(target_p).startswith(str(resolved_root)):
                            raise ValueError(f"Security violation: path traversal detected in zip member: {member.filename}")
                    z.extractall(REPO_ROOT)
                tmp_zip.unlink(missing_ok=True)
                extracted_dir = REPO_ROOT / "MoGe-main"
                if extracted_dir.exists():
                    if moge_dir.exists():
                        shutil.rmtree(moge_dir, ignore_errors=True)
                    extracted_dir.rename(moge_dir)
        print("  [OK] Upstream MoGe repository ready.")


def package_and_stage_extension():
    print("[SETUP] Packaging and checking Blender extension...")
    ext_installer = REPO_ROOT / "tools" / "install_extension.py"
    if ext_installer.exists():
        run_cmd([sys.executable, str(ext_installer)], "Packaging extension & staging to Blender", check=False)


def create_desktop_shortcut():
    """Create a Windows Desktop shortcut for MoDe 3D Studio."""
    if sys.platform != "win32":
        return
    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            return
        shortcut_path = desktop / "MoDe 3D Studio.lnk"
        launcher_bat = REPO_ROOT / "Start_MoDe_3D.bat"
        if not launcher_bat.exists():
            return

        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{str(shortcut_path)}'); "
            f"$s.TargetPath = '{str(launcher_bat)}'; "
            f"$s.WorkingDirectory = '{str(REPO_ROOT)}'; "
            f"$s.Description = 'Launch MoDe 3D Studio for Blender'; "
            f"$s.Save()"
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        print(f"  [OK] Created Desktop shortcut: {shortcut_path.name}")
    except Exception as e:
        print(f"[WARN] Could not create Desktop shortcut: {e}")


def launch_daemon(no_launch: bool = False):
    create_desktop_shortcut()
    if daemon_already_running():
        print_banner("MoDe 3D Studio is READY!")
        print(f"""
  AI Engine Daemon already running on: http://{DAEMON_HOST}:{DAEMON_PORT}

  Open Blender and press Generate — no need to start a second engine.
""")
        return
    if no_launch:
        print_banner("MoDe 3D Studio is READY!")
        print("""
  Installed without launching (--no-launch).

  Start later with Start_MoDe_3D, or let Blender auto-start the engine
  when you click 'Generate 3D Splats'.
""")
        return
    print_banner("MoDe 3D Studio is READY!")
    print("""
  AI Engine Daemon is running on: http://127.0.0.1:8766
  
  HOW TO USE IN BLENDER:
  1. Open Blender (version 4.2+ or 5.x).
  2. If not already enabled, go to Edit > Preferences > Extensions
     and enable 'MoDe 3D Studio' (or 'Install from Disk': dist/moge_splat_studio.zip).
  3. In the 3D Viewport, press 'N' to open the sidebar panel.
  4. Switch to the 'MoDe 3D' tab.
  5. Select an image and click 'Generate 3D Splats'!

  (Cold-start is now active: if you close this window, clicking 'Generate 3D'
   in Blender will automatically launch the engine in the background!)
""")
    print("=" * 70 + "\n")
    daemon_args = [sys.executable, str(DAEMON_SCRIPT), "--host", DAEMON_HOST, "--port", str(DAEMON_PORT), "--preload", "v3"]
    subprocess.run(daemon_args, cwd=str(REPO_ROOT))


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="MoDe 3D Studio one-click setup & launch")
    ap.add_argument("--no-launch", action="store_true", help="Install/stage only, do not start the daemon")
    ap.add_argument("--check", action="store_true", help="Verify environment and exit (no install, no launch)")
    ap.add_argument("--uninstall", action="store_true", help="Remove staged extension, configs and shortcut")
    args = ap.parse_args(argv)

    if args.uninstall:
        sys.exit(uninstall_all())

    print_banner("MoDe 3D Studio - One-Click Setup & Launch")

    if args.check:
        venv_py = get_venv_python()
        vi = sys.version_info
        print(f"  system python: {vi.major}.{vi.minor}.{vi.micro} ({sys.executable})")
        print(f"  venv present: {venv_py.exists()} ({venv_py})")
        print(f"  daemon already running: {daemon_already_running()}")
        sys.exit(0)

    # Step 1: Ensure we are inside the virtual environment.
    # Bootstrap interpreter may be newer than the supported range; only enforce
    # the pin when creating a fresh venv or running inside it.
    venv_py = get_venv_python()
    if not is_running_in_target_venv():
        if not VENV_DIR.exists():
            check_python_version()
        ensure_venv()
        if venv_py.exists():
            # Re-launch this script inside the venv (forward CLI flags)
            cmd = [str(venv_py), str(Path(__file__).resolve())] + (argv if argv is not None else sys.argv[1:])
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
            sys.exit(proc.returncode)
        else:
            print("[WARN] Could not find venv python; continuing with current environment.")
    else:
        check_python_version()

    # Step 2: Install dependencies
    check_and_install_dependencies()

    # Step 3: Package & stage Blender extension
    package_and_stage_extension()

    # Step 4: Launch Warm GPU Daemon (or stop before it with --no-launch)
    launch_daemon(no_launch=args.no_launch)


if __name__ == "__main__":
    main()
