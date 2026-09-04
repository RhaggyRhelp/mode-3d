# Project Etiquette & Coding Standards: MoGe Splat Studio

This document defines the strict engineering contract for all AI agents and developers working on this codebase.

## 1. Modular Boundaries (No Monoliths)
* **UI Changes (`ui.py` & `properties.py`):**
  * When changing labels, tooltips, or layouts, modify only `ui.py` and `properties.py`.
  * **Rule:** Change visible `name="..."` and `text="..."` labels freely. NEVER change internal Enum keys (e.g. `"NORMAL"`, `"SEAMLESS"`) without explicit migration logic.
* **Shader & Node Tree Changes (`nodes.py`):**
  * Geometry Nodes, Material BSDF, and Compositor nodes live exclusively in `nodes.py`.
* **Execution & Operators (`operators.py`):**
  * Operator logic lives in `operators.py`. Never add heavy computation directly to UI draw methods.
* **Storage & Cache (`cleanup.py`):**
  * All temporary files MUST be routed through `cleanup.get_active_scan_dir()`.
  * Never invent new temporary folders in `%TEMP%` or write intermediate files to project root.
* **Daemon & Networking (`network.py` & `daemon/`):**
  * Daemon communication lives in `network.py`.

## 2. Zero Hardcoding Policy (Portability)
* **Never hardcode personal paths:**
  * Absolute paths like `C:\Users\...` or `E:\...` are strictly prohibited.
  * Use `Path(__file__).resolve().parents[...]`, `Path.home()`, `os.environ`, or Addon Preferences.
* **Virtual Environments:**
  * Auto-start discovery must inspect `MOGE_PY`, Addon Preferences, and relative `.venv` candidates before attempting to launch. Never assume a specific user's folder exists.

## 3. Error Handling & Transparency
* **No Silent Swallowing:**
  * Bare `except Exception: pass` is forbidden for core operators and network calls.
  * Report meaningful errors using `self.report({'ERROR'}, ...)` or `self.report({'WARNING'}, ...)`.

## 4. Pre-Commit Verification Gate
* Before committing or finishing any code modification:
  1. Run unit tests: `python tests/test_protocol.py`
  2. Run headless Blender verification: `blender --factory-startup --background --python tools/test_headless_blender.py`
  3. Verify `git status` contains NO `.obj`, `.npz`, `.zip`, `.pyc`, or render images.
