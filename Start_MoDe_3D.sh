#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "======================================================================"
echo "  MoDe 3D Studio - Starting One-Click Launcher..."
echo "======================================================================"

if command -v python3 >/dev/null 2>&1; then
    PY_BOOTSTRAP=python3
elif command -v python >/dev/null 2>&1; then
    PY_BOOTSTRAP=python
else
    echo "[ERROR] Python 3 was not detected on your system."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

"$PY_BOOTSTRAP" tools/one_click_setup.py "$@"
