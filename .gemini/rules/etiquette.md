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
  * Bare `except:` or `except Exception: pass` is forbidden for core operators, network calls, and file I/O.
  * Report meaningful errors using `self.report({'ERROR'}, ...)`, `self.report({'WARNING'}, ...)`, or logger tracebacks.

## 4. Blender 5.2 Extension Compliance & Non-Blocking Architecture
* **Extension Format:**
  * Extensions must rely strictly on `blender_manifest.toml`. Do not duplicate metadata in legacy `bl_info`.
  * Declare required permissions in `blender_manifest.toml` (e.g. `[permissions] network = "..."`).
* **Non-Blocking UI:**
  * Long-running network or compute operations (such as `/infer`) MUST be implemented as non-blocking modal operators (`invoke()` + worker thread + `TIMER` event handling). Never block Blender's main event loop with synchronous network wait loops.
* **Process Lifecycle:**
  * Any background daemon spawned by the extension must register `bpy.app.handlers.exit_pre` to prevent orphaned background processes upon Blender exit.

## 5. Single Source of Truth for Constants
* Do not duplicate mathematical or protocol constants between `operators.py` and `shared/protocol.py`. Import them or keep them unified.

## 6. Pre-Commit Verification Gate
* Before committing or finishing any code modification:
  1. Run unit test suite:
     * `python tests/test_protocol.py`
     * `python tests/test_daemon_variants.py`
     * `python tests/test_floor.py`
     * `python tests/test_push.py`
  2. Run hygiene check: `python tools/health_check.py` (all tiers must pass).
  3. Run headless Blender verification: `blender --factory-startup --background --python tools/test_headless_blender.py`
  4. Verify `git status` contains NO `.obj`, `.npz`, `.zip`, `.pyc`, or render images.
