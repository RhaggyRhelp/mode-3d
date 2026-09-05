"""Self-cleaning and storage manager for MoGe Splat Studio.

Ensures zero accumulation of temporary scan payloads on disk,
and purges unreferenced Blender data-blocks (meshes, materials, images, node groups).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
import bpy
from bpy.types import Operator


def get_cache_root() -> Path:
    """Deterministic single-directory cache for all MoGe scans."""
    cache = Path(tempfile.gettempdir()) / "moge_splat_studio_cache"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def get_active_scan_dir() -> Path:
    """Directory containing the currently active scan payload."""
    active = get_cache_root() / "active"
    active.mkdir(parents=True, exist_ok=True)
    return active


def prepare_new_scan_cache() -> Path:
    """Wipes previous active temporary scan payload so disk junk never accumulates."""
    active = get_active_scan_dir()
    if active.exists():
        for item in active.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except Exception as e:
                print(f"[MoGe Splat Studio] cache wipe skipped {item}: {e}")

    active.mkdir(parents=True, exist_ok=True)
    return active


def get_cache_size_mb() -> float:
    """Compute total disk size consumed by MoGe temporary caches."""
    total_bytes = 0
    cache_root = get_cache_root()
    if cache_root.exists():
        for p in cache_root.rglob("*"):
            if p.is_file():
                try:
                    total_bytes += p.stat().st_size
                except Exception as e:
                    print(f"[MoGe Splat Studio] cache size stat skipped {p}: {e}")

    return total_bytes / (1024.0 * 1024.0)


def purge_all_temporary_storage() -> tuple[float, int]:
    """Purge all MoGe disk cache, logs, and temp files within the studio cache root."""
    bytes_freed = 0
    files_removed = 0

    cache_root = get_cache_root()
    if cache_root.exists():
        for p in list(cache_root.rglob("*")):
            if p.is_file():
                try:
                    bytes_freed += p.stat().st_size
                    files_removed += 1
                except Exception as e:
                    print(f"[MoGe Splat Studio] purge stat skipped {p}: {e}")
        shutil.rmtree(cache_root, ignore_errors=True)

    # Clean legacy log/pid if present in system temp
    temp_root = Path(tempfile.gettempdir())
    for fname in ("moge_daemon.log", "moge_daemon.pid"):
        fpath = temp_root / fname
        if fpath.exists():
            try:
                bytes_freed += fpath.stat().st_size
                fpath.unlink(missing_ok=True)
                files_removed += 1
            except Exception as e:
                print(f"[MoGe Splat Studio] legacy temp cleanup skipped {fpath}: {e}")

    return bytes_freed / (1024.0 * 1024.0), files_removed


def purge_orphaned_blender_datablocks() -> int:
    """Purge all unreferenced MoGe meshes, materials, images, and node groups."""
    removed_count = 0

    # Meshes
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0 and ("MoGe" in mesh.name or "Splat" in mesh.name):
            try:
                bpy.data.meshes.remove(mesh)
                removed_count += 1
            except Exception as e:
                print(f"[MoGe Splat Studio] mesh purge skipped {mesh.name}: {e}")

    # Materials
    for mat in list(bpy.data.materials):
        if mat.users == 0 and "MoGe" in mat.name:
            try:
                bpy.data.materials.remove(mat)
                removed_count += 1
            except Exception as e:
                print(f"[MoGe Splat Studio] material purge skipped {mat.name}: {e}")

    # Cameras
    for cam in list(bpy.data.cameras):
        if cam.users == 0 and "MoGe" in cam.name:
            try:
                bpy.data.cameras.remove(cam)
                removed_count += 1
            except Exception as e:
                print(f"[MoGe Splat Studio] camera purge skipped {cam.name}: {e}")

    # Images (Strictly scoped to MoGe-generated plates and cache files)
    for img in list(bpy.data.images):
        if img.users == 0 and (
            bool(img.get("is_moge")) or
            img.name.startswith("MoGe_") or
            "moge_splat_studio_cache" in (getattr(img, "filepath", "") or "").lower()
        ):
            try:
                bpy.data.images.remove(img)
                removed_count += 1
            except Exception as e:
                print(f"[MoGe Splat Studio] image purge skipped {img.name}: {e}")

    # Node Groups (Geometry Nodes & Compositor trees)
    for ng in list(bpy.data.node_groups):
        if ng.users == 0 and ("MoGe" in ng.name or "Splat" in ng.name):
            try:
                bpy.data.node_groups.remove(ng)
                removed_count += 1
            except Exception as e:
                print(f"[MoGe Splat Studio] node-group purge skipped {ng.name}: {e}")

    return removed_count


class MOGE_OT_purge_all_cache(Operator):
    """Purge all temporary disk scan cache and clean orphaned Blender datablocks"""
    bl_idname = "moge_splat.purge_all_cache"
    bl_label = "Purge Cache & Clean Data"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mb_freed, files_removed = purge_all_temporary_storage()
        blocks_removed = purge_orphaned_blender_datablocks()

        if hasattr(context.scene, "moge_splat_props"):
            props = context.scene.moge_splat_props
            props.cache_size_mb = 0.0
            props.last_scan_points = 0
            props.last_scan_fov = ""
            props.last_scan_model = ""
            props.last_scan_depth_range = ""
            props.last_scan_folder = ""
            props.last_scanned_image = ""

        msg = f"Purged {mb_freed:.1f} MB disk cache ({files_removed} files) and {blocks_removed} unused Blender blocks."
        print(f"[MoGe Splat Studio] {msg}")
        self.report({'INFO'}, msg)
        return {'FINISHED'}
