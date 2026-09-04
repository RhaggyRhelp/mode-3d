"""Render comparison of sphere normal shading vs flat surface normal shading on point splats."""
import sys
from pathlib import Path
sys.path.insert(0, r"E:\MOGE")

import bpy
import math
import numpy as np
from tests.render_surfel_comparison import build_splat_mesh, setup_render_scene

out_dir = Path(r"E:\MOGE\tests\output_mesh_test")

bpy.ops.wm.read_factory_settings(use_empty=False)
bpy.data.objects.remove(bpy.data.objects['Cube'], do_unlink=True)

obj = build_splat_mesh("Splats_Points_NormalShaded")

# GN Tree: simple native points
ng = bpy.data.node_groups.new(name="GN_Points_Test", type="GeometryNodeTree")
ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
to_pts = ng.nodes.new("GeometryNodeMeshToPoints")
set_r = ng.nodes.new("GeometryNodeSetPointRadius")
nat_r = ng.nodes.new("GeometryNodeInputNamedAttribute")
nat_r.data_type = "FLOAT"
nat_r.inputs["Name"].default_value = "SplatRadius"
inp = ng.nodes.new("NodeGroupInput")
out_n = ng.nodes.new("NodeGroupOutput")

# Material with Surface Normal shading instead of Sphere normal
mat = bpy.data.materials.new("Mat_Point_NormalShaded")
mat.use_nodes = True
mat.node_tree.nodes.clear()
m_out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
m_bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
m_bsdf.inputs["Roughness"].default_value = 0.8

# Color
m_vc = mat.node_tree.nodes.new("ShaderNodeAttribute")
m_vc.attribute_name = "Color"
mat.node_tree.links.new(m_vc.outputs["Color"], m_bsdf.inputs["Base Color"])

# Plug MoGe's predicted surface normal into the BSDF normal!
m_norm = mat.node_tree.nodes.new("ShaderNodeAttribute")
m_norm.attribute_name = "SplatNormal"
mat.node_tree.links.new(m_norm.outputs["Vector"], m_bsdf.inputs["Normal"])

mat.node_tree.links.new(m_bsdf.outputs["BSDF"], m_out.inputs["Surface"])

set_m = ng.nodes.new("GeometryNodeSetMaterial")
set_m.inputs["Material"].default_value = mat

ng.links.new(inp.outputs[0], to_pts.inputs["Mesh"])
ng.links.new(to_pts.outputs["Points"], set_r.inputs["Points"])
ng.links.new(nat_r.outputs["Attribute"], set_r.inputs["Radius"])
ng.links.new(set_r.outputs["Points"], set_m.inputs["Geometry"])
ng.links.new(set_m.outputs["Geometry"], out_n.inputs[0])

mod = obj.modifiers.new(name="Viewer", type="NODES")
mod.node_group = ng

# Add a sun light so we can clearly see the shading behavior
light_data = bpy.data.lights.new(name="SunLight", type='SUN')
light_data.energy = 2.0
light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45.0), math.radians(30.0), 0.0)

setup_render_scene(obj, out_dir / "render_points_surface_normal_shaded.png")
print("Rendered Normal-Shaded Points!")
