"""Render comparison of Isotropic Point Spheres vs Oriented Gaussian Surfel Discs in Blender 5.2."""
import sys
from pathlib import Path
sys.path.insert(0, r"E:\MOGE")

import bpy
import math
import numpy as np
from tests.test_surfel_splats import create_gaussian_material, create_surfel_node_group

out_dir = Path(r"E:\MOGE\tests\output_mesh_test")
npz_path = out_dir / "01_HouseIndoor.npz"

data = np.load(npz_path)
points = data["points"]
depth = data["depth"]
normal = data["normal"]
intrinsics = data["intrinsics"]
image = data["image"]

h, w = depth.shape[:2]
fx = intrinsics[0, 0] * w
fy = intrinsics[1, 1] * h
cx = intrinsics[0, 2] * w
cy = intrinsics[1, 2] * h

# Stride by 2 (~100k points)
stride = 2
us, vs = np.meshgrid(np.arange(0, w, stride), np.arange(0, h, stride))
d_sub = depth[::stride, ::stride]
n_sub = normal[::stride, ::stride]
c_sub = image[::stride, ::stride] / 255.0

finite = np.isfinite(d_sub) & (d_sub > 0.05)
X = (us[finite] - cx) * d_sub[finite] / fx
Y = (vs[finite] - cy) * d_sub[finite] / fy
Z = d_sub[finite]

# Blender coordinates: X right, Y depth, Z up
xyz_bl = np.stack([X, Z, -Y], axis=-1).astype(np.float32)
norms_bl = np.stack([n_sub[finite, 0], n_sub[finite, 2], -n_sub[finite, 1]], axis=-1).astype(np.float32)
n_len = np.linalg.norm(norms_bl, axis=-1, keepdims=True)
norms_bl = np.where(n_len > 1e-6, norms_bl / np.maximum(n_len, 1e-6), np.array([0, 0, 1], dtype=np.float32))

cols = c_sub[finite].astype(np.float32)
# Adaptive radius: depth / fx * 1.6
radii = (d_sub[finite] / fx * 1.8).astype(np.float32)

N_pts = len(xyz_bl)
print(f"Building splat object with {N_pts:,} points...")

def build_splat_mesh(name):
    m = bpy.data.meshes.new(name + "_Mesh")
    m.vertices.add(N_pts)
    m.vertices.foreach_set("co", xyz_bl.ravel())
    m.update()

    cattr = m.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    c_rgba = np.ones((N_pts, 4), dtype=np.float32)
    c_rgba[:, :3] = cols
    cattr.data.foreach_set("color", c_rgba.ravel())

    rattr = m.attributes.new(name="SplatRadius", type="FLOAT", domain="POINT")
    rattr.data.foreach_set("value", radii.ravel())

    nattr = m.attributes.new(name="SplatNormal", type="FLOAT_VECTOR", domain="POINT")
    nattr.data.foreach_set("vector", norms_bl.ravel())

    dattr = m.attributes.new(name="SplatDepth", type="FLOAT", domain="POINT")
    dattr.data.foreach_set("value", Z.ravel())

    obj = bpy.data.objects.new(name, m)
    bpy.context.collection.objects.link(obj)
    return obj

def setup_render_scene(obj, out_png):
    scene = bpy.context.scene
    cam = scene.camera
    # Camera stepped forward and right for a distinct 3D parallax view of the wall and floor
    cam.location = (0.5, -0.3, 0.1)
    cam.rotation_euler = (math.radians(82.0), 0.0, math.radians(16.0))
    cam.data.angle = math.radians(65.0)
    cam.data.clip_end = 100.0

    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 683
    scene.render.filepath = str(out_png)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_png.name}")

# --- Render 1: Current Point Spheres ---
bpy.ops.wm.read_factory_settings(use_empty=False)
bpy.data.objects.remove(bpy.data.objects['Cube'], do_unlink=True)
obj_spheres = build_splat_mesh("Splats_Spheres")

ng_spheres = bpy.data.node_groups.new(name="GN_Spheres", type="GeometryNodeTree")
ng_spheres.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng_spheres.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
to_pts = ng_spheres.nodes.new("GeometryNodeMeshToPoints")
set_r = ng_spheres.nodes.new("GeometryNodeSetPointRadius")
nat_r = ng_spheres.nodes.new("GeometryNodeInputNamedAttribute")
nat_r.data_type = "FLOAT"
nat_r.inputs["Name"].default_value = "SplatRadius"
inp = ng_spheres.nodes.new("NodeGroupInput")
out_n = ng_spheres.nodes.new("NodeGroupOutput")

mat_s = bpy.data.materials.new("Mat_Spheres")
mat_s.use_nodes = True
mat_s.node_tree.nodes.clear()
m_out = mat_s.node_tree.nodes.new("ShaderNodeOutputMaterial")
m_bsdf = mat_s.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
m_bsdf.inputs["Roughness"].default_value = 0.8
m_vc = mat_s.node_tree.nodes.new("ShaderNodeAttribute")
m_vc.attribute_name = "Color"
mat_s.node_tree.links.new(m_vc.outputs["Color"], m_bsdf.inputs["Base Color"])
mat_s.node_tree.links.new(m_bsdf.outputs["BSDF"], m_out.inputs["Surface"])

set_m = ng_spheres.nodes.new("GeometryNodeSetMaterial")
set_m.inputs["Material"].default_value = mat_s

ng_spheres.links.new(inp.outputs[0], to_pts.inputs["Mesh"])
ng_spheres.links.new(to_pts.outputs["Points"], set_r.inputs["Points"])
ng_spheres.links.new(nat_r.outputs["Attribute"], set_r.inputs["Radius"])
ng_spheres.links.new(set_r.outputs["Points"], set_m.inputs["Geometry"])
ng_spheres.links.new(set_m.outputs["Geometry"], out_n.inputs[0])

mod = obj_spheres.modifiers.new(name="Viewer", type="NODES")
mod.node_group = ng_spheres

setup_render_scene(obj_spheres, out_dir / "render_splats_spheres.png")

# --- Render 2: Oriented Gaussian Surfels ---
bpy.ops.wm.read_factory_settings(use_empty=False)
bpy.data.objects.remove(bpy.data.objects['Cube'], do_unlink=True)
obj_surfels = build_splat_mesh("Splats_Surfels")

mat_gauss = create_gaussian_material()
ng_surfels = create_surfel_node_group(mat_gauss)

mod2 = obj_surfels.modifiers.new(name="Surfel_Viewer", type="NODES")
mod2.node_group = ng_surfels

setup_render_scene(obj_surfels, out_dir / "render_splats_surfels.png")
print("ALL DONE!")
