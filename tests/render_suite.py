"""Render side-by-side comparison of baseline, guided filtered, and planar decimated meshes in Blender."""
import bpy
import math
from pathlib import Path

out_dir = Path(__file__).resolve().parent / "output_mesh_test"

def render_scene(obj_path, out_png, show_wireframe=False):
    bpy.ops.wm.read_factory_settings(use_empty=False)
    scene = bpy.context.scene
    bpy.data.objects.remove(bpy.data.objects['Cube'], do_unlink=True)

    # Import OBJ with correct forward Y, up Z
    fpath = str(obj_path).replace("\\", "/")
    bpy.ops.wm.obj_import(filepath=fpath, forward_axis='Y', up_axis='Z')
    mesh_objs = [o for o in scene.objects if o.type == 'MESH']
    if not mesh_objs:
        return
    obj = mesh_objs[0]

    # Camera at camera center (0, 0, 0) looking along +Y
    cam = scene.camera
    cam.location = (0.0, 0.0, 0.0)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    cam.data.angle = math.radians(65.0)

    # Add directional grazing light to reveal surface ripples
    light = [o for o in scene.objects if o.type == 'LIGHT'][0]
    light.location = (1.2, 0.5, 0.8)
    light.data.energy = 40.0

    # Shading
    for p in obj.data.polygons:
        p.use_smooth = True

    if show_wireframe:
        wire = obj.modifiers.new("Wire", 'WIREFRAME')
        wire.thickness = 0.002
        wire.use_replace = False

    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 683
    scene.render.filepath = str(out_png)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_png.name}")

render_scene(out_dir / "01_baseline_raw.obj", out_dir / "render_01_raw.png")
render_scene(out_dir / "02_guided_filtered.obj", out_dir / "render_02_filtered.png")
render_scene(out_dir / "04_planar_decimated.obj", out_dir / "render_04_decimated.png")
render_scene(out_dir / "04_planar_decimated.obj", out_dir / "render_04_wireframe.png", show_wireframe=True)
