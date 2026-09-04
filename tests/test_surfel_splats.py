"""Test script to compare standard point-sphere splats vs oriented Gaussian surfel splats in Blender."""
import bpy
import math
import numpy as np
from pathlib import Path

out_dir = Path(r"E:\MOGE\tests\output_mesh_test")

def create_gaussian_material():
    mat = bpy.data.materials.get("M_MoGe_Gaussian_Splat")
    if mat is None:
        mat = bpy.data.materials.new(name="M_MoGe_Gaussian_Splat")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")

    # Vertex Color
    attr_col = nodes.new("ShaderNodeAttribute")
    attr_col.attribute_name = "Color"
    links.new(attr_col.outputs["Color"], bsdf.inputs["Base Color"])

    # Surfel local coordinates (X, Y in [-1, 1])
    attr_coord = nodes.new("ShaderNodeAttribute")
    attr_coord.attribute_name = "SurfelCoord"

    # r^2 = x^2 + y^2
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(attr_coord.outputs["Vector"], sep.inputs["Vector"])

    mul_x = nodes.new("ShaderNodeMath")
    mul_x.operation = "MULTIPLY"
    links.new(sep.outputs["X"], mul_x.inputs[0])
    links.new(sep.outputs["X"], mul_x.inputs[1])

    mul_y = nodes.new("ShaderNodeMath")
    mul_y.operation = "MULTIPLY"
    links.new(sep.outputs["Y"], mul_y.inputs[0])
    links.new(sep.outputs["Y"], mul_y.inputs[1])

    r_sq = nodes.new("ShaderNodeMath")
    r_sq.operation = "ADD"
    links.new(mul_x.outputs["Value"], r_sq.inputs[0])
    links.new(mul_y.outputs["Value"], r_sq.inputs[1])

    # Gaussian: exp(-3.0 * r^2)
    mul_k = nodes.new("ShaderNodeMath")
    mul_k.operation = "MULTIPLY"
    links.new(r_sq.outputs["Value"], mul_k.inputs[0])
    mul_k.inputs[1].default_value = -3.0

    gauss_alpha = nodes.new("ShaderNodeMath")
    gauss_alpha.operation = "EXPONENT"
    links.new(mul_k.outputs["Value"], gauss_alpha.inputs[0])

    links.new(gauss_alpha.outputs["Value"], bsdf.inputs["Alpha"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # Material settings
    try:
        mat.blend_method = 'BLEND'
    except Exception:
        pass
    return mat

def create_surfel_node_group(mat):
    gname = "MoGe_Surfel_Viewer"
    ng = bpy.data.node_groups.get(gname)
    if ng is None:
        ng = bpy.data.node_groups.new(name=gname, type="GeometryNodeTree")
    ng.interface.clear()
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    inp = nodes.new("NodeGroupInput")
    out = nodes.new("NodeGroupOutput")

    to_pts = nodes.new("GeometryNodeMeshToPoints")

    # Instance quad / disc
    circle = nodes.new("GeometryNodeMeshCircle")
    circle.fill_type = "NGON"
    circle.inputs["Vertices"].default_value = 8
    circle.inputs["Radius"].default_value = 1.0

    # Store SurfelCoord attribute on the circle mesh so the shader has local radial UV
    store_coord = nodes.new("GeometryNodeStoreNamedAttribute")
    store_coord.data_type = "FLOAT_VECTOR"
    store_coord.inputs["Name"].default_value = "SurfelCoord"
    pos = nodes.new("GeometryNodeInputPosition")
    links.new(circle.outputs["Mesh"], store_coord.inputs["Geometry"])
    links.new(pos.outputs["Position"], store_coord.inputs["Value"])

    # Normal orientation
    align = nodes.new("FunctionNodeAlignEulerToVector")
    align.axis = "Z"
    nat_norm = nodes.new("GeometryNodeInputNamedAttribute")
    nat_norm.data_type = "FLOAT_VECTOR"
    nat_norm.inputs["Name"].default_value = "SplatNormal"
    links.new(nat_norm.outputs["Attribute"], align.inputs["Vector"])

    # Radius scale
    nat_rad = nodes.new("GeometryNodeInputNamedAttribute")
    nat_rad.data_type = "FLOAT"
    nat_rad.inputs["Name"].default_value = "SplatRadius"

    # Instance on points
    inst = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(inp.outputs[0], to_pts.inputs["Mesh"])
    links.new(to_pts.outputs["Points"], inst.inputs["Points"])
    links.new(store_coord.outputs["Geometry"], inst.inputs["Instance"])
    links.new(align.outputs["Rotation"], inst.inputs["Rotation"])
    links.new(nat_rad.outputs["Attribute"], inst.inputs["Scale"])

    # Material
    set_m = nodes.new("GeometryNodeSetMaterial")
    set_m.inputs["Material"].default_value = mat
    links.new(inst.outputs["Instances"], set_m.inputs["Geometry"])
    links.new(set_m.outputs["Geometry"], out.inputs[0])

    return ng

print("Surfel definitions compiled cleanly.")
