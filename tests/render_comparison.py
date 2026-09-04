"""Headless Blender script to render side-by-side clay/normal visualization of raw vs reconstructed mesh."""
import bpy
import math
import sys
from pathlib import Path

out_dir = Path(r"E:\MOGE\tests\output_mesh_test")
raw_path = out_dir / "01_baseline_raw.obj"
clean_path = out_dir / "04_planar_decimated.obj"

def render_mesh(obj_path, out_png):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 683
    scene.render.filepath = str(out_png)

    # Import OBJ
    fpath = str(obj_path).replace("\\", "/")
    bpy.ops.wm.obj_import(filepath=fpath)

    mesh_objs = [o for o in scene.objects if o.type == 'MESH']
    if not mesh_objs:
        print("No mesh imported!")
        return
    obj = mesh_objs[0]

    # Material: Clean clay / smooth shading with directional lighting
    mat = bpy.data.materials.new(name="ClayMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.75, 0.72, 0.68, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.35
    obj.data.materials.append(mat)

    # Shading: smooth
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Camera at origin looking forward (+Y depth, +Z up in Blender)
    cam_data = bpy.data.cameras.new(name="Cam")
    cam_data.angle = math.radians(65.0)
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.location = (0.0, -0.2, 0.0)
    cam_obj.rotation_euler = (math.radians(85.0), 0.0, 0.0)

    # Light: Sun lamp at grazing angle to clearly show undulations / bumps
    light_data = bpy.data.lights.new(name="Sun", type='SUN')
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("Sun", light_data)
    scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(45.0), math.radians(30.0), math.radians(60.0))

    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_png}")

if raw_path.exists():
    render_mesh(raw_path, out_dir / "render_01_baseline_raw.png")
if clean_path.exists():
    render_mesh(clean_path, out_dir / "render_04_planar_decimated.png")
