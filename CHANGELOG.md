# Changelog

All notable changes to MoDe 3D Studio. Versions follow semver; Blender extension,
daemon (`FastAPI` title version) and `pyproject` are bumped together.

## [2.2.0]
### Fixed
- Keep-Transform floor parenting: `matrix_parent_inverse = parent_world⁻¹`, basis untouched
  (was double-transforming splats/camera on level).
- Resolution shortcut buttons no longer force preset to `Custom` (stamp-guarded, re-snaps match).
- Worker thread never touches `bpy.*`: native colors preloaded on main thread, network/numpy
  off-thread; cooperative ESC cancel + progress + VRAM/CUDA gate.
- `cleanup.py` / scan paths log instead of swallowing errors.
### Added
- Wire `PROTOCOL_VERSION = 2` in `/health` + `.npz` (backward-compatible read of v1).
- Setup flags `--no-launch/--check/--uninstall`, duplicate-daemon guard, `cu128→cu121`
  torch fallback, shallow MoGe clone, full dep check.
- Blender 5.2 compliance: manifest-only (no `bl_info`), `[permissions] network`,
  `exit_pre` daemon cleanup.
- CI (`py_compile` + pure-numpy pytest + optional Blender validate), `.gitattributes`.
### Docs
- Pano/zoom sections marked FUTURE/roadmap-only (were incorrectly shipped).
- README: flags, troubleshooting (`:8766`, firewall, Giant+4K), protocol note.

## [2.1.0]
- Modular rewrite: warm GPU daemon + point-splat addon + self-cleaning cache.
- See `docs/AMENDED_PLAN_v2.1.md` for the v2.1 scope.
