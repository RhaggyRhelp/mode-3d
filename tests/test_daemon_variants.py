"""Daemon variant map + eviction safety (no GPU: never loads weights)."""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "daemon"))
sys.path.insert(0, str(REPO_ROOT))

import moge_daemon as D


def test_pretrained_map():
    assert D.PRETRAINED[("v3", "vitl")] == "Ruicheng/moge-3-vitl"
    assert D.PRETRAINED[("v3", "vitg")] == "Ruicheng/moge-3-vitg"
    assert D.PRETRAINED[("v2", "vitl")] == "Ruicheng/moge-2-vitl-normal"
    assert set(D.VARIANTS) == {"vitl", "vitg"}


def test_unknown_rejected_before_gpu():
    for v, u in [("v9", "vitl"), ("v3", "vitx")]:
        try:
            D.get_model(v, u)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {v}/{u}")
    assert D.MODELS == {}, "must not have loaded anything"


def test_evict_missing_safe():
    D._evict(("v3", "vitl"))  # no-op, must not touch CUDA


def test_protocol_giant():
    from shared.protocol import PRESETS
    g = PRESETS["Giant"]
    assert g["variant"] == "vitg" and g["model_version"] == "v3"
    assert PRESETS["Balanced"]["variant"] == "vitl"


def test_main_guard_present():
    src = (REPO_ROOT / "daemon" / "moge_daemon.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = False
    for node in tree.body:
        if isinstance(node, ast.If):
            t = ast.dump(node.test)
            if "__name__" in t and "__main__" in t:
                found = True
    assert found, "top-level if __name__ == '__main__' guard missing!"


if __name__ == "__main__":
    test_pretrained_map()
    test_unknown_rejected_before_gpu()
    test_evict_missing_safe()
    test_protocol_giant()
    test_main_guard_present()
    print("daemon-variant tests OK")
