"""Pytest configuration and environment fixtures for MoGe Splat Studio tests."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "daemon", REPO_ROOT / "shared"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
