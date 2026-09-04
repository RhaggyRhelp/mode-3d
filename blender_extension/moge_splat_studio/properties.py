"""Scene property definitions for MoGe Splat Studio."""
from __future__ import annotations

import bpy
from bpy.props import (
    StringProperty,
    FloatProperty,
    BoolProperty,
    EnumProperty,
    IntProperty,
)
from bpy.types import PropertyGroup

PRESET_VALUES = {
    "Draft": {"model_version": "v3", "variant": "vitl", "resolution_level": "Low", "refine_steps": 0, "max_size": 1024, "tta": "off", "point_budget": 1200000},
    "Balanced": {"model_version": "v3", "variant": "vitl", "resolution_level": "High", "refine_steps": 2, "max_size": 1536, "tta": "off", "point_budget": 1200000},
    "Quality": {"model_version": "v3", "variant": "vitl", "resolution_level": "High", "refine_steps": 3, "max_size": 2448, "tta": "off", "point_budget": 2000000},
    "Max Quality": {"model_version": "v3", "variant": "vitg", "resolution_level": "High", "refine_steps": 7, "max_size": 4096, "tta": "flip", "point_budget": 4000000},
}
_STAMPING_PRESET = False


def _apply_preset(self, context):
    global _STAMPING_PRESET
    vals = PRESET_VALUES.get(self.preset)
    if not vals:
        return
    _STAMPING_PRESET = True
    try:
        self.model_version = vals["model_version"]
        self.model_variant = vals.get("variant", "vitl")
        self.resolution_level = vals["resolution_level"]
        self.refine_steps = vals["refine_steps"]
        self.max_size = vals["max_size"]
        if "tta" in vals:
            self.tta_mode = vals["tta"]
        if "point_budget" in vals:
            self.point_budget = vals["point_budget"]
    finally:
        _STAMPING_PRESET = False


def _mark_custom(self, context):
    if _STAMPING_PRESET:
        return
    try:
        if self.preset != "Custom":
            self.preset = "Custom"
    except Exception:
        pass


class MoGeSplatProperties(PropertyGroup):
    ui_mode: EnumProperty(
        name="Mode",
        description="Switch between Simple (clean workflow) and Advanced (full parameter control)",
        items=[
            ("SIMPLE", "Simple", "Clean, one-click workflow with essential settings"),
            ("ADVANCED", "Advanced", "Full control: all parameters, boxes, and diagnostics exposed"),
        ],
        default="SIMPLE",
    )
    import_path: StringProperty(name="Source Image", subtype="FILE_PATH", default="")
    preset: EnumProperty(
        name="Preset",
        items=[
            ("Draft", "Draft (Fast <1.0s)", "Sub-second preview scrub: MoGe-3, 1024px, 0 iterations"),
            ("Balanced", "Balanced (Recommended)", "MoGe-3 Standard, 1536px, 2 iterations (~1.8s)"),
            ("Quality", "Quality (2.5K Crisp)", "MoGe-3 Standard, 2448px, 3 iterations (~3.2s)"),
            ("Max Quality", "Max Quality (4K Hero)", "All-out hero preset: Giant ViT-G, 4096px, 7 iterations, 2x pass, 4M pts"),
            ("Custom", "Custom", "You tweaked a field by hand"),
        ],
        default="Balanced",
        update=_apply_preset,
    )
    model_version: EnumProperty(
        name="Model Version",
        description="Underlying MoGe model architecture (MoGe-3 is recommended for all modern scans)",
        items=[
            ("v3", "MoGe-3", "Latest state-of-the-art geometry model"),
            ("v2", "MoGe-2", "Legacy model"),
        ],
        default="v3",
        update=_mark_custom,
    )
    model_variant: EnumProperty(
        name="AI Model Quality",
        description="AI model architecture size. Standard is fast with balanced VRAM (~2.5 GB); Giant provides maximum micro-detail (~7 GB VRAM)",
        items=[
            ("vitl", "Standard (Fast / 2.5GB)", "MoGe-3 Large: fast, balanced VRAM"),
            ("vitg", "Giant (Ultra Detail / 7GB)", "MoGe-3 Giant: maximum detail, ~7GB VRAM"),
        ],
        default="vitl",
        update=_mark_custom,
    )
    resolution_level: EnumProperty(
        name="Feature Separation",
        description="How finely the AI detects small geometric features. High detects thin table legs, wires, and window frames without blending them into backgrounds",
        items=[
            ("Low", "Low", "Fewest detail tokens, fastest"),
            ("Medium", "Medium", "Balanced detail"),
            ("High", "High", "Sharpest geometric creases & thin feature separation"),
        ],
        default="High",
        update=_mark_custom,
    )
    refine_steps: IntProperty(
        name="Geometry Iterations",
        description="Number of self-refinement passes (0 to 7). 0: raw draft; 2: balanced (flattens walls & removes ripples); 3: sharp edges; 7: maximum surface convergence and crispest silhouettes",
        default=2,
        min=0,
        max=7,
        update=_mark_custom,
    )
    max_size: IntProperty(
        name="Resolution (px)",
        description="Long-edge pixel resolution for 3D point generation (1536 Standard, 2448 2.5K, 4096 4K). Denser resolution produces more raw points",
        default=1536,
        min=512,
        max=4096,
        update=_mark_custom,
    )
    surface_mode: EnumProperty(
        name="Environment Boundary",
        description="Controls boundary clipping and sky filtering for the 3D scene",
        items=[
            ("SEAMLESS", "Full Room (Seamless)", "Watertight, 0 holes. Connects background smoothly to foreground (best for rooms & architectural interiors)"),
            ("MASKED", "Cut Sky (Masked)", "Automatically removes background skies and infinite depth voids (best for outdoor & street scenes)"),
            ("ISLANDS", "Separate Objects (Islands)", "Severs stretched skins to turn props and characters into isolated floating 3D objects"),
        ],
        default="SEAMLESS",
    )
    apply_mask: BoolProperty(
        name="Cut Background Voids",
        description="Drops background skies and depth voids while splitting objects",
        default=False,
    )
    use_custom_fov: BoolProperty(
        name="Manual Camera Lens (FOV)",
        description="Override automatic EXIF lens detection with a manual horizontal field of view",
        default=False,
    )
    custom_fov: FloatProperty(
        name="Lens FOV (deg)",
        description="Horizontal field of view in degrees (e.g. 50mm lens ~ 40°, 24mm wide-angle ~ 74°)",
        default=60.0,
        min=5.0,
        max=160.0,
    )
    shading_mode: EnumProperty(
        name="Lighting & Shading",
        description="Lighting for points: Lit (reacts smoothly to scene lights) or Unlit (photo color only)",
        items=[
            ("NORMAL", "Lit (Reacts to Scene Lights)", "Points receive Blender scene light; walls & floors shade flat via SplatNormal"),
            ("UNLIT", "Unlit (Photo Color Only)", "Flat color emission matching the photo, zero scene shadows"),
        ],
        default="NORMAL",
    )
    splat_style: EnumProperty(
        name="Geometry Style",
        description="Splat primitive: Smooth 3D Points (60+ FPS) or Oriented Discs (Surfels)",
        items=[
            ("SPHERES", "Smooth 3D Points", "Smooth screen-space points, fast 60+ FPS navigation"),
            ("SURFELS", "Oriented Discs (Surfels)", "Flat polygonal discs aligned to surface normals"),
        ],
        default="SPHERES",
    )
    splat_radius: FloatProperty(
        name="Fixed Radius (m)",
        description="0 = Auto-Depth Adaptive (close points are sharp, distant points expand to fill gaps). >0 forces all points to an exact fixed size",
        default=0.0,
        min=0.0,
        max=0.5,
    )
    radius_scale: FloatProperty(
        name="Gap Fill Scale",
        description="Multiplier on point sizes. Increase (1.2-1.5) to close distant pinholes; decrease (0.7-0.9) for pin-sharp fine detail",
        default=1.0,
        min=0.2,
        max=3.0,
    )
    point_budget: IntProperty(
        name="Max Viewport Points",
        description="Maximum points imported into Blender to preserve smooth viewport navigation (e.g. 1.2M for 60 FPS, 4M for high-density rendering)",
        default=1200000,
        min=50000,
        max=12000000,
    )
    fullres_color: BoolProperty(
        name="High-Res Source Colors",
        description="Samples vertex colors directly from your native high-resolution photo file on disk instead of the AI downscale. Delivers maximum texture sharpness with 0 extra VRAM cost",
        default=True,
    )
    daemon_autostart: BoolProperty(
        name="Auto-Start AI Engine",
        description="If the background GPU AI engine is down when you hit Generate, start it automatically",
        default=True,
    )
    tta_mode: EnumProperty(
        name="Anti-Jitter Passes",
        description="Multi-pass inference to cancel noise and camera bias. 2x mirrors image to cut noise; 3x adds a downscaled pass for cleanest edge silhouettes",
        items=[
            ("off", "Off (Single Pass)", "Fastest, standard scan"),
            ("flip", "2x Mirror Pass (~2x time)", "Base + mirror, mean-fused (cuts jitter in half)"),
            ("flip3", "3x Clean Pass (~3x time)", "Base + mirror + 0.8x view, median-fused (cleanest edges)"),
        ],
        default="off",
        update=_mark_custom,
    )
    last_scan_folder: StringProperty(default="")
    last_scanned_image: StringProperty(default="")
    cache_size_mb: FloatProperty(name="Cache Size (MB)", default=0.0)
    last_scan_points: IntProperty(name="Last Scan Points", default=0)
    last_scan_model: StringProperty(name="Last Scan Model", default="")
    last_scan_depth_range: StringProperty(name="Last Scan Depth Range", default="")
    last_scan_fov: StringProperty(name="Last Scan FOV", default="")
