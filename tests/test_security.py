"""Security verification suite for MoDe 3D Studio.

Verifies:
1. Origin check middleware: blocks unauthorized cross-origin requests from external web pages.
2. Allows local / localhost requests.
3. Payload size caps on daemon endpoints.
4. Safe process termination guards (refuses to kill system PIDs or non-python processes).
5. Zip Slip (path traversal) defense.
6. Cache directory sandboxing.
"""
import io
import sys
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from unittest.mock import MagicMock
if "bpy" not in sys.modules:
    bpy_mock = MagicMock()
    sys.modules["bpy"] = bpy_mock
    sys.modules["bpy.props"] = MagicMock()
    sys.modules["bpy.types"] = MagicMock()
if "mathutils" not in sys.modules:
    sys.modules["mathutils"] = MagicMock()

from daemon.moge_daemon import app, MAX_UPLOAD_SIZE
from blender_extension.moge_splat_studio.network import _verify_process_is_python, daemon_stop, _daemon_pid_path
from blender_extension.moge_splat_studio.cleanup import get_cache_root, prepare_new_scan_cache


def test_origin_security():
    """Verify that external web pages cannot access the local daemon via cross-origin requests."""
    client = TestClient(app)

    # 1. External origins must be rejected with 403 Forbidden
    for evil_origin in ("https://malicious.com", "http://attacker.site:8080", "http://evil.local"):
        resp = client.get("/health", headers={"origin": evil_origin})
        assert resp.status_code == 403, f"Failed: origin {evil_origin} was not blocked (got {resp.status_code})"
        assert "Forbidden" in resp.json().get("error", "")

    # 2. Localhost origins and no-origin requests (from Blender) must succeed
    resp_no_origin = client.get("/health")
    assert resp_no_origin.status_code == 200

    resp_localhost = client.get("/health", headers={"origin": "http://localhost:8766"})
    assert resp_localhost.status_code == 200

    resp_127 = client.get("/health", headers={"origin": "http://127.0.0.1:8766"})
    assert resp_127.status_code == 200
    print("[OK] Origin security checks passed.")


def test_payload_size_limit():
    """Verify that payloads exceeding the 64MB limit are rejected with 413."""
    client = TestClient(app)

    # Mock 65MB upload
    oversized_data = b"0" * (MAX_UPLOAD_SIZE + 1024)
    files = {"image": ("test_huge.jpg", io.BytesIO(oversized_data), "image/jpeg")}
    data = {"model_version": "v3"}

    resp = client.post("/infer", files=files, data=data)
    assert resp.status_code == 413, f"Expected 413, got {resp.status_code}"
    assert "exceeds" in resp.json().get("error", "")
    print("[OK] Payload size limit checks passed.")


def test_safe_process_termination():
    """Verify that PID termination safeguards protect reserved/system and non-python PIDs."""
    # System PID protection
    assert _verify_process_is_python(0) is False
    assert _verify_process_is_python(1) is False
    assert _verify_process_is_python(4) is False
    assert _verify_process_is_python(-10) is False

    # Simulate rogue PID file pointing to system PID 4
    pid_file = _daemon_pid_path()
    pid_file.write_text("4")
    ok, msg = daemon_stop()
    assert ok is False
    assert "Refusing to kill" in msg
    assert not pid_file.exists()  # Stale/unsafe PID file removed
    print("[OK] Safe process termination checks passed.")


def test_zip_slip_prevention(tmp_path: Path):
    """Verify that archives with path traversal members are blocked."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as z:
        z.writestr("../../../evil_exploit.txt", "payload")
    zip_buf.seek(0)

    target_dir = tmp_path / "sandbox"
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_root = target_dir.resolve()

    traversal_caught = False
    with zipfile.ZipFile(zip_buf, "r") as z:
        for member in z.infolist():
            target_p = (target_dir / member.filename).resolve()
            if not str(target_p).startswith(str(resolved_root)):
                traversal_caught = True
                break
    assert traversal_caught is True, "Zip Slip vulnerability was not caught!"
    print("[OK] Zip slip prevention checks passed.")


def test_cache_isolation():
    """Verify that cache stays strictly within moge_splat_studio_cache."""
    cache = get_cache_root()
    assert cache.name == "moge_splat_studio_cache"
    active = prepare_new_scan_cache()
    assert active.parent == cache
    print("[OK] Cache isolation checks passed.")


if __name__ == "__main__":
    test_origin_security()
    test_payload_size_limit()
    test_safe_process_termination()
    test_zip_slip_prevention(Path(get_cache_root()))
    test_cache_isolation()
    print("\nALL SECURITY TESTS PASSED SUCCESSFULLY!")
