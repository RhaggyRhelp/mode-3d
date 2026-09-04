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
    """Wipes previous temporary scan payloads so disk junk never accumulates.

    Called immediately before a new scan begins.
    """
    # 1. Clean active directory
    active = get_active_scan_dir()
    for item in active.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception:
            pass

    # 2. Scrub any legacy loose scan folders in tempdir
    try:
        temp_root = Path(tempfile.gettempdir())
        for prefix in ("moge_splat_*", "moge_direct_*"):
            for old_dir in temp_root.glob(prefix):
                if old_dir.is_dir():
                    shutil.rmtree(old_dir, ignore_errors=True)
    except Exception:
        pass

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
                except Exception:
                    pass

    # Also check legacy folders
    temp_root = Path(tempfile.gettempdir())
    for prefix in ("moge_splat_*", "moge_direct_*"):
        for old_dir in temp_root.glob(prefix):
            if old_dir.is_dir():
                for p in old_dir.rglob("*"):
                    if p.is_file():
                        try:
                            total_bytes += p.stat().st_size
                        except Exception:
                            pass

    return total_bytes / (1024.0 * 1024.0)


def purge_all_temporary_storage() -> tuple[float, int]:
    """Purge all MoGe disk cache, logs, and temp files. Returns (mb_freed, files_removed)."""
    bytes_freed = 0
    files_removed = 0

    cache_root = get_cache_root()
    if cache_root.exists():
        for p in list(cache_root.rglob("*")):
            if p.is_file():
                try:
                    bytes_freed += p.stat().st_size
                    files_removed += 1
                except Exception:
                    pass
        shutil.rmtree(cache_root, ignore_errors=True)

    temp_root = Path(tempfile.gettempdir())
    for prefix in ("moge_splat_*", "moge_direct_*"):
        for old_dir in list(temp_root.glob(prefix)):
            if old_dir.is_dir():
                for p in list(old_dir.rglob("*")):
                    if p.is_file():
                        try:
                            bytes_freed += p.stat().st_size
                            files_removed += 1
                        except Exception:
                            pass
                shutil.rmtree(old_dir, ignore_errors=True)

    # Clean daemon log/pid if safe
    for fname in ("moge_daemon.log", "moge_daemon.pid"):
        fpath = temp_root / fname
        if fpath.exists():
            try:
                bytes_freed += fpath.stat().st_size
                fpath.unlink(missing_ok=True)
                files_removed += 1
            except Exception:
                pass

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
            except Exception:
                pass

    # Materials
    for mat in list(bpy.data.materials):
        if mat.users == 0 and "MoGe" in mat.name:
            try:
                bpy.data.materials.remove(mat)
                removed_count += 1
            except Exception:
                pass

    # Images
    for img in list(bpy.data.images):
        if img.users == 0 and ("moge" in img.name.lower() or "splat" in img.name.lower() or img.name in ("image.png", "normal.png")):
            try:
                bpy.data.images.remove(img)
                removed_count += 1
            except Exception:
                pass

    # Node Groups (Geometry Nodes & Compositor trees)
    for ng in list(bpy.data.node_groups):
        if ng.users == 0 and ("MoGe" in ng.name or "Splat" in ng.name):
            try:
                bpy.data.node_groups.remove(ng)
                removed_count += 1
            except Exception:
                pass

    return removed_count


class MOGE_OT_purge_all_cache(Operator):
    """Purge all temporary disk scan cache and clean orphaned Blender datablocks"""
    bl_idname = "moge_splat.purge_all_cache"
    bl_label = "Purge Cache & Clean Data"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mb_freed, files_removed = purge_all_temporary_storage()
        blocks_removed = purge_orphaned_blender_datablocks()

        msg = f"Purged {mb_freed:.1f} MB disk cache ({files_removed} files) and {blocks_removed} unused Blender blocks."
        print(f"[MoGe Splat Studio] {msg}")
        self.report({'INFO'}, msg)
        return {'FINISHED'}
