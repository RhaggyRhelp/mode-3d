"""Package and optionally stage the Blender 4.2+ / 5.x extension.

Cross-platform script (Windows, Linux, macOS) that builds the extension zip
and automatically stages it to the user's local Blender extensions directory.
"""
from __future__ import annotations

import os
import sys
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "blender_extension" / "moge_splat_studio"
DIST = ROOT / "dist"
OUT_ZIP = DIST / "moge_splat_studio.zip"


def find_blender_extension_dir() -> Path | None:
    """Find the user_default extensions directory for the highest Blender 4.2+ version."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        base = Path(appdata) / "Blender Foundation" / "Blender"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Blender"
    else:
        base = Path.home() / ".config" / "blender"

    if not base.exists():
        return None

    # Search for version directories (e.g., 5.2, 5.1, 4.3, 4.2)
    versions = []
    for d in base.iterdir():
        if d.is_dir():
            try:
                parts = [int(p) for p in d.name.split(".")]
                if len(parts) >= 2 and (parts[0] > 4 or (parts[0] == 4 and parts[1] >= 2)):
                    versions.append((parts, d))
            except ValueError:
                pass

    if not versions:
        return None

    versions.sort(key=lambda x: x[0], reverse=True)
    best_ver_dir = versions[0][1]
    return best_ver_dir / "extensions" / "user_default" / "moge_splat_studio"


def write_persistent_config(stage_dir: Path | None = None):
    """Write machine-specific paths so Blender can auto-start the daemon without manual setup."""
    daemon_script = ROOT / "daemon" / "moge_daemon.py"
    if sys.platform == "win32":
        venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = ROOT / ".venv" / "bin" / "python"

    py_bin = str(venv_py) if venv_py.exists() else str(venv_py.resolve())
    daemon_bin = str(daemon_script) if daemon_script.exists() else str(daemon_script.resolve())
    repo_bin = str(ROOT) if ROOT.exists() else str(ROOT.resolve())

    config_data = {
        "repo_root": repo_bin,
        "daemon_script": daemon_bin,
        "python_bin": py_bin,
    }

    import json

    # 1. Global user config (~/.mode_3d/config.json)
    try:
        global_cfg_dir = Path.home() / ".mode_3d"
        global_cfg_dir.mkdir(parents=True, exist_ok=True)
        global_cfg_file = global_cfg_dir / "config.json"
        with open(global_cfg_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"[CONFIG] Registered persistent environment to: {global_cfg_file}")
    except Exception as e:
        print(f"[WARN] Could not write global config: {e}")

    # 2. Staged extension config
    if stage_dir and stage_dir.exists():
        try:
            stage_cfg_file = stage_dir / "mode_3d_config.json"
            with open(stage_cfg_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            print(f"[CONFIG] Registered extension config to: {stage_cfg_file}")
        except Exception as e:
            print(f"[WARN] Could not write staged config: {e}")


def main():
    assert (SRC / "__init__.py").exists(), f"missing {SRC / '__init__.py'}"
    assert (SRC / "blender_manifest.toml").exists(), f"missing {SRC / 'blender_manifest.toml'}"

    DIST.mkdir(exist_ok=True)
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SRC.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc") and p.name != "mode_3d_config.json":
                arcname = f"moge_splat_studio/{p.relative_to(SRC).as_posix()}"
                z.write(p, arcname=arcname)

    print(f"[BUILD] Built extension zip: {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024:.1f} KB)")

    stage = find_blender_extension_dir()
    if stage:
        stage.mkdir(parents=True, exist_ok=True)
        # Copy directory tree cleanly
        for item in SRC.rglob("*"):
            if "__pycache__" in item.parts or item.name.endswith(".pyc"):
                continue
            rel = item.relative_to(SRC)
            target = stage / rel
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, target)
        print(f"[STAGE] Successfully staged to: {stage}")
        print("        Restart Blender or Reload Scripts, then enable 'MoDe 3D Studio'.")
    else:
        print("[INFO] Blender extensions directory not automatically detected.")
        print(f"       Install manually in Blender via Edit > Preferences > Extensions > Install from Disk: {OUT_ZIP}")

    # Register persistent config for both global profile and staged extension
    write_persistent_config(stage)


if __name__ == "__main__":
    main()
