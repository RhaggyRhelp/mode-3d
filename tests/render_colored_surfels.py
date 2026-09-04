"""Render colored Gaussian surfel discs in Blender 5.2."""
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
import math
import numpy as np
from tests.render_surfel_comparison import build_splat_mesh, setup_render_scene, create_gaussian_material

out_dir = Path(__file__).resolve().parent / "output_mesh_test"

bpy.ops.wm.read_factory_settings(use_empty=False)
bpy.data.objects.remove(bpy.data.objects['Cube'], do_unlink=True)

obj = build_splat_mesh("Splats_Surfels_Color")

# Build surfel node tree with Realize Instances so Color passes to vertices
ng = bpy.data.node_groups.new(name="MoGe_Surfel_Viewer_Color", type="GeometryNodeTree")
ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

inp = ng.nodes.new("NodeGroupInput")
out = ng.nodes.new("NodeGroupOutput")
to_pts = ng.nodes.new("GeometryNodeMeshToPoints")

circle = ng.nodes.new("GeometryNodeMeshCircle")
circle.fill_type = "NGON"
circle.inputs["Vertices"].default_value = 6 # 6-sided disc
circle.inputs["Radius"].default_value = 2.4 # overlap factor to close gaps

store_coord = ng.nodes.new("GeometryNodeStoreNamedAttribute")
store_coord.data_type = "FLOAT_VECTOR"
store_coord.inputs["Name"].default_value = "SurfelCoord"
pos = ng.nodes.new("GeometryNodeInputPosition")
ng.links.new(circle.outputs["Mesh"], store_coord.inputs["Geometry"])
ng.links.new(pos.outputs["Position"], store_coord.inputs["Value"])

align = ng.nodes.new("FunctionNodeAlignEulerToVector")
align.axis = "Z"
nat_norm = ng.nodes.new("GeometryNodeInputNamedAttribute")
nat_norm.data_type = "FLOAT_VECTOR"
nat_norm.inputs["Name"].default_value = "SplatNormal"
ng.links.new(nat_norm.outputs["Attribute"], align.inputs["Vector"])

nat_rad = ng.nodes.new("GeometryNodeInputNamedAttribute")
nat_rad.data_type = "FLOAT"
nat_rad.inputs["Name"].default_value = "SplatRadius"

inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
ng.links.new(inp.outputs[0], to_pts.inputs["Mesh"])
ng.links.new(to_pts.outputs["Points"], inst.inputs["Points"])
ng.links.new(store_coord.outputs["Geometry"], inst.inputs["Instance"])
ng.links.new(align.outputs["Rotation"], inst.inputs["Rotation"])
ng.links.new(nat_rad.outputs["Attribute"], inst.inputs["Scale"])

# Realize instances so Color attribute propagates
realize = ng.nodes.new("GeometryNodeRealizeInstances")
ng.links.new(inst.outputs["Instances"], realize.inputs["Geometry"])

# Set material
mat = create_gaussian_material()
set_m = ng.nodes.new("GeometryNodeSetMaterial")
set_m.inputs["Material"].default_value = mat
ng.links.new(realize.outputs["Geometry"], set_m.inputs["Geometry"])
ng.links.new(set_m.outputs["Geometry"], out.inputs[0])

mod = obj.modifiers.new(name="Surfel_Viewer", type="NODES")
mod.node_group = ng

setup_render_scene(obj, out_dir / "render_splats_surfels_color.png")
print("Rendered Color Surfels successfully!")
