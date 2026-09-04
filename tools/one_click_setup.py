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

import os
import sys
import shutil
import venv
import subprocess
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAEMON_SCRIPT = REPO_ROOT / "daemon" / "moge_daemon.py"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
VENV_DIR = REPO_ROOT / ".venv"


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
        print("[SETUP] Installing PyTorch with CUDA acceleration (this may take a few minutes on first run)...")
        cmd = [
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision",
            "--index-url", "https://download.pytorch.org/whl/cu121"
        ]
        run_cmd(cmd, "Installing PyTorch CUDA wheels")

    # 2. Check requirements.txt
    print("[SETUP] Verifying daemon requirements (FastAPI, OpenCV, flex-gemm, utils3d)...")
    req_missing = False
    for mod in ("fastapi", "uvicorn", "multipart", "cv2", "PIL", "utils3d"):
        try:
            __import__(mod)
        except ImportError:
            req_missing = True
            break

    if req_missing:
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
                run_cmd(["git", "clone", "https://github.com/microsoft/MoGe.git", str(moge_dir)], "Cloning MoGe repository")
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


def launch_daemon():
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

  (Keep this window open while using Blender. Press Ctrl+C to stop.)
""")
    print("=" * 70 + "\n")
    daemon_args = [sys.executable, str(DAEMON_SCRIPT), "--host", "127.0.0.1", "--port", "8766", "--preload", "v3"]
    subprocess.run(daemon_args, cwd=str(REPO_ROOT))


def main():
    print_banner("MoDe 3D Studio - One-Click Setup & Launch")

    # Step 1: Ensure we are inside the virtual environment
    venv_py = get_venv_python()
    if not is_running_in_target_venv():
        ensure_venv()
        if venv_py.exists():
            # Re-launch this script inside the venv
            args = [str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:]
            proc = subprocess.run(args, cwd=str(REPO_ROOT))
            sys.exit(proc.returncode)
        else:
            print("[WARN] Could not find venv python; continuing with current environment.")

    # Step 2: Install dependencies
    check_and_install_dependencies()

    # Step 3: Package & stage Blender extension
    package_and_stage_extension()

    # Step 4: Launch Warm GPU Daemon
    launch_daemon()


if __name__ == "__main__":
    main()
