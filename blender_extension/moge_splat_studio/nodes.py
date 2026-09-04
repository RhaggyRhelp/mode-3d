"""Geometry Nodes, Material, and Compositor graph generators for MoGe Splat Studio."""
from __future__ import annotations

import bpy
import numpy as np
from pathlib import Path


def ensure_splat_material(shading_mode: str = "NORMAL") -> bpy.types.Material:
    mat = bpy.data.materials.get("M_MoGe_Splat")
    if mat is None:
        mat = bpy.data.materials.new(name="M_MoGe_Splat")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new(type="ShaderNodeOutputMaterial")
    out.location = (650, 0)

    vc = nodes.new(type="ShaderNodeAttribute")
    vc.location = (-250, 100)
    vc.attribute_name = "Color"
    try:
        vc.attribute_type = "GEOMETRY"
    except Exception:
        pass

    if shading_mode == "UNLIT":
        emit = nodes.new(type="ShaderNodeEmission")
        emit.location = (150, 0)
        emit.inputs["Strength"].default_value = 1.0
        try:
            links.new(vc.outputs["Color"], emit.inputs["Color"])
            links.new(emit.outputs["Emission"], out.inputs["Surface"])
        except Exception:
            pass
        return mat

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    try:
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 0.8
    except Exception:
        pass
    try:
        links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    except Exception:
        pass

    if shading_mode == "NORMAL":
        try:
            attr_norm = nodes.new(type="ShaderNodeAttribute")
            attr_norm.location = (-400, -350)
            attr_norm.attribute_name = "SplatNormal"
            try:
                attr_norm.attribute_type = "GEOMETRY"
            except Exception:
                pass

            vec_norm = nodes.new(type="ShaderNodeVectorMath")
            vec_norm.operation = "NORMALIZE"
            vec_norm.location = (-200, -350)
            links.new(attr_norm.outputs["Vector"], vec_norm.inputs[0])

            vec_trans = nodes.new(type="ShaderNodeVectorTransform")
            vec_trans.vector_type = "NORMAL"
            vec_trans.convert_from = "OBJECT"
            vec_trans.convert_to = "WORLD"
            vec_trans.location = (0, -350)
            links.new(vec_norm.outputs["Vector"], vec_trans.inputs["Vector"])
            links.new(vec_trans.outputs["Vector"], bsdf.inputs["Normal"])
        except Exception as e:
            print(f"[MoGe] Splat normal hook warning: {e}")

    try:
        links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    except Exception:
        pass
    try:
        mat.blend_method = 'HASHED'
    except Exception:
        pass
    return mat


def ensure_splat_node_group(radius: float) -> bpy.types.NodeTree:
    gname = "MoGe_Splat_Viewer"
    ng = bpy.data.node_groups.get(gname)
    if ng is None:
        ng = bpy.data.node_groups.new(name=gname, type="GeometryNodeTree")
    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    gin = nodes.new(type="NodeGroupInput")
    gin.location = (-600, 0)
    gout = nodes.new(type="NodeGroupOutput")
    gout.location = (500, 0)

    def _has_socket(want_in_out: str) -> bool:
        for s in ng.interface.items_tree:
            if getattr(s, "name", "") == "Geometry" and getattr(s, "in_out", "") == want_in_out:
                return True
        return False

    if not _has_socket("INPUT"):
        ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    if not _has_socket("OUTPUT"):
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    to_pts = nodes.new(type="GeometryNodeMeshToPoints")
    to_pts.location = (-300, 0)
    to_pts.mode = "VERTICES"

    set_r = nodes.new(type="GeometryNodeSetPointRadius")
    set_r.location = (-100, 0)
    try:
        set_r.inputs["Radius"].default_value = float(radius)
    except Exception:
        set_r.inputs[2].default_value = float(radius)

    set_mat = nodes.new(type="GeometryNodeSetMaterial")
    set_mat.location = (150, 0)
    set_mat.inputs["Material"].default_value = ensure_splat_material()

    links.new(gin.outputs["Geometry"], to_pts.inputs["Mesh"])
    links.new(to_pts.outputs["Points"], set_r.inputs["Points"])
    links.new(set_r.outputs["Points"], set_mat.inputs["Geometry"])

    out_sock = next((s for s in gout.inputs if "Geometr" in s.name or s.bl_idname == "NodeSocketGeometry"), None)
    if out_sock:
        links.new(set_mat.outputs["Geometry"], out_sock)

    return ng


def ensure_splat_node_group_v2(fallback_radius: float) -> bpy.types.NodeTree:
    gname = "MoGe_Splat_Viewer_v2"
    ng = bpy.data.node_groups.get(gname)
    if ng is None:
        ng = bpy.data.node_groups.new(name=gname, type="GeometryNodeTree")
    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    gin = nodes.new(type="NodeGroupInput")
    gin.location = (-700, 0)
    gout = nodes.new(type="NodeGroupOutput")
    gout.location = (600, 0)

    def _has_socket(want_in_out: str) -> bool:
        for s in ng.interface.items_tree:
            if getattr(s, "name", "") == "Geometry" and getattr(s, "in_out", "") == want_in_out:
                return True
        return False

    if not _has_socket("INPUT"):
        ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    if not _has_socket("OUTPUT"):
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    to_pts = nodes.new(type="GeometryNodeMeshToPoints")
    to_pts.location = (-400, 0)
    to_pts.mode = "VERTICES"

    nat = nodes.new(type="GeometryNodeInputNamedAttribute")
    nat.location = (-400, -250)
    nat.data_type = "FLOAT"
    nat.inputs[0].default_value = "SplatRadius"

    fclamp = nodes.new(type="ShaderNodeClamp")
    fclamp.location = (-200, -150)
    fclamp.inputs["Min"].default_value = 0.001
    fclamp.inputs["Max"].default_value = 0.06

    set_r = nodes.new(type="GeometryNodeSetPointRadius")
    set_r.location = (0, 0)
    try:
        set_r.inputs["Radius"].default_value = float(fallback_radius)
    except Exception:
        set_r.inputs[2].default_value = float(fallback_radius)

    set_mat = nodes.new(type="GeometryNodeSetMaterial")
    set_mat.location = (250, 0)
    set_mat.inputs["Material"].default_value = ensure_splat_material()

    links.new(gin.outputs["Geometry"], to_pts.inputs["Mesh"])
    links.new(to_pts.outputs["Points"], set_r.inputs["Points"])
    links.new(nat.outputs[0], fclamp.inputs["Value"])
    links.new(fclamp.outputs["Result"], set_r.inputs["Radius"])
    links.new(set_r.outputs["Points"], set_mat.inputs["Geometry"])

    out_sock = next((s for s in gout.inputs if "Geometr" in s.name or s.bl_idname == "NodeSocketGeometry"), None)
    if out_sock:
        links.new(set_mat.outputs["Geometry"], out_sock)

    return ng


def ensure_splat_node_group_surfels(fallback_radius: float) -> bpy.types.NodeTree:
    gname = "MoGe_Surfel_Viewer"
    ng = bpy.data.node_groups.get(gname)
    if ng is None:
        ng = bpy.data.node_groups.new(name=gname, type="GeometryNodeTree")
    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    gin = nodes.new(type="NodeGroupInput")
    gin.location = (-700, 0)
    gout = nodes.new(type="NodeGroupOutput")
    gout.location = (800, 0)

    def _has_socket(want_in_out: str) -> bool:
        for s in ng.interface.items_tree:
            if getattr(s, "name", "") == "Geometry" and getattr(s, "in_out", "") == want_in_out:
                return True
        return False

    if not _has_socket("INPUT"):
        ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    if not _has_socket("OUTPUT"):
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    to_pts = nodes.new(type="GeometryNodeMeshToPoints")
    to_pts.location = (-500, 0)

    circle = nodes.new(type="GeometryNodeMeshCircle")
    circle.location = (-500, -250)
    circle.fill_type = "NGON"
    circle.inputs["Vertices"].default_value = 6
    circle.inputs["Radius"].default_value = 1.0

    store_coord = nodes.new(type="GeometryNodeStoreNamedAttribute")
    store_coord.location = (-300, -250)
    store_coord.data_type = "FLOAT_VECTOR"
    store_coord.inputs["Name"].default_value = "SurfelCoord"

    pos = nodes.new(type="GeometryNodeInputPosition")
    pos.location = (-500, -400)
    links.new(circle.outputs["Mesh"], store_coord.inputs["Geometry"])
    links.new(pos.outputs["Position"], store_coord.inputs["Value"])

    align = nodes.new(type="FunctionNodeAlignEulerToVector")
    align.location = (-100, 150)
    align.axis = "Z"

    nat_norm = nodes.new(type="GeometryNodeInputNamedAttribute")
    nat_norm.location = (-300, 150)
    nat_norm.data_type = "FLOAT_VECTOR"
    nat_norm.inputs["Name"].default_value = "SplatNormal"
    links.new(nat_norm.outputs["Attribute"], align.inputs["Vector"])

    nat_rad = nodes.new(type="GeometryNodeInputNamedAttribute")
    nat_rad.location = (-300, -50)
    nat_rad.data_type = "FLOAT"
    nat_rad.inputs["Name"].default_value = "SplatRadius"

    fclamp = nodes.new(type="ShaderNodeClamp")
    fclamp.location = (-100, -50)
    fclamp.inputs["Min"].default_value = 0.001
    fclamp.inputs["Max"].default_value = 0.06
    links.new(nat_rad.outputs[0], fclamp.inputs["Value"])

    inst = nodes.new(type="GeometryNodeInstanceOnPoints")
    inst.location = (150, 0)
    links.new(gin.outputs["Geometry"], to_pts.inputs["Mesh"])
    links.new(to_pts.outputs["Points"], inst.inputs["Points"])
    links.new(store_coord.outputs["Geometry"], inst.inputs["Instance"])
    links.new(align.outputs["Rotation"], inst.inputs["Rotation"])
    links.new(fclamp.outputs["Result"], inst.inputs["Scale"])

    realize = nodes.new(type="GeometryNodeRealizeInstances")
    realize.location = (350, 0)
    links.new(inst.outputs["Instances"], realize.inputs["Geometry"])

    set_mat = nodes.new(type="GeometryNodeSetMaterial")
    set_mat.location = (550, 0)
    set_mat.inputs["Material"].default_value = ensure_splat_material()
    links.new(realize.outputs["Geometry"], set_mat.inputs["Geometry"])

    out_sock = next((s for s in gout.inputs if "Geometr" in s.name or s.bl_idname == "NodeSocketGeometry"), None)
    if out_sock:
        links.new(set_mat.outputs["Geometry"], out_sock)

    return ng


def set_splat_radius_all(radius: float):
    for gname in ("MoGe_Splat_Viewer", "MoGe_Splat_Viewer_v2"):
        ng = bpy.data.node_groups.get(gname)
        if ng is None:
            continue
        for n in ng.nodes:
            if n.bl_idname == "GeometryNodeSetPointRadius":
                try:
                    n.inputs["Radius"].default_value = float(radius)
                except Exception:
                    try:
                        n.inputs[2].default_value = float(radius)
                    except Exception:
                        pass


def new_splat_object(
    context, xyz, rgb01, depths, radii, fx_px, radius_scale,
    radius_fallback, warn=None, extra_attrs=None,
    obj_name="MoGe_Splats", normals=None, splat_style="SPHERES",
    shading_mode="NORMAL",
):
    xyz = np.asarray(xyz, dtype=np.float32)
    rgb01 = np.asarray(rgb01, dtype=np.float32)
    n = int(xyz.shape[0])

    mesh = bpy.data.meshes.new(name=obj_name + "_Mesh")
    mesh.vertices.add(n)
    flat_co = np.empty(n * 3, dtype=np.float32)
    flat_co[0::3] = xyz[:, 0]
    flat_co[1::3] = xyz[:, 1]
    flat_co[2::3] = xyz[:, 2]
    mesh.vertices.foreach_set("co", flat_co)
    mesh.update()

    cattr = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    flat_col = np.empty(n * 4, dtype=np.float32)
    flat_col[0::4] = rgb01[:, 0]
    flat_col[1::4] = rgb01[:, 1]
    flat_col[2::4] = rgb01[:, 2]
    flat_col[3::4] = 1.0
    cattr.data.foreach_set("color", flat_col)

    # Point attributes
    items = [
        ("SplatDepth", np.asarray(depths, dtype=np.float32)),
        ("SplatRadius", np.asarray(radii, dtype=np.float32)),
    ]
    if extra_attrs:
        for aname, avals in extra_attrs.items():
            items.append((aname, np.asarray(avals, dtype=np.float32)))

    for aname, avals in items:
        attr = mesh.attributes.new(name=aname, type="FLOAT", domain="POINT")
        attr.data.foreach_set("value", np.ascontiguousarray(avals, dtype=np.float32))

    if normals is not None:
        nattr = mesh.attributes.new(name="SplatNormal", type="FLOAT_VECTOR", domain="POINT")
        nattr.data.foreach_set("vector", np.ascontiguousarray(normals, dtype=np.float32).ravel())

    obj = bpy.data.objects.new(obj_name, mesh)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.location = (0.0, 0.0, 0.0)

    obj["moge_fx_px"] = float(fx_px)
    obj["moge_radius_scale"] = float(radius_scale)
    obj["moge_splat_style"] = str(splat_style)
    obj["moge_shading_mode"] = str(shading_mode)
    obj["moge_splat_version"] = 3

    if splat_style == "SURFELS" and normals is not None:
        ng = ensure_splat_node_group_surfels(radius_fallback)
    else:
        ng = ensure_splat_node_group_v2(radius_fallback)

    mod = obj.modifiers.new(name="MoGe_Splat_Viewer", type="NODES")
    mod.node_group = ng

    mat = ensure_splat_material(shading_mode)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return obj


def setup_compositor_relighter(context, img_file: Path, norm_file: Path) -> tuple[bool, str]:
    tree = None
    if hasattr(context.scene, "compositing_node_group") and context.scene.compositing_node_group:
        tree = context.scene.compositing_node_group
    if tree is None and hasattr(context.scene, "node_tree") and context.scene.node_tree:
        tree = context.scene.node_tree
    if tree is None:
        tree = bpy.data.node_groups.get("Compositor Nodes")
    if tree is None:
        tree = bpy.data.node_groups.new(name="Compositor Nodes", type="CompositorNodeTree")

    if hasattr(context.scene, "compositing_node_group"):
        context.scene.compositing_node_group = tree
    if hasattr(context.scene, "use_nodes"):
        context.scene.use_nodes = True
    context.scene.render.use_compositing = True

    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    def _first(sockcoll, name, bl_idname):
        for s in sockcoll:
            if s.name == name and s.bl_idname == bl_idname:
                return s
        return None

    def make_mix():
        n = nodes.new(type="ShaderNodeMix")
        try:
            n.data_type = "RGBA"
        except Exception:
            pass
        return n

    def mix_color(blend, a_out, b_out, x, y, label=""):
        m = make_mix()
        m.location = (x, y)
        if label:
            m.label = label
        m.blend_type = blend
        fac = _first(m.inputs, "Factor", "NodeSocketFloatFactor") or m.inputs[0]
        A = _first(m.inputs, "A", "NodeSocketColor")
        B = _first(m.inputs, "B", "NodeSocketColor")
        R = _first(m.outputs, "Result", "NodeSocketColor")
        if A is None or B is None or R is None:
            raise RuntimeError("Unified Mix lacks required color sockets.")
        try:
            fac.default_value = 1.0
        except Exception:
            pass
        links.new(a_out, A)
        links.new(b_out, B)
        return m, R

    def make_math():
        return nodes.new(type="ShaderNodeMath")

    def make_val():
        return nodes.new(type="ShaderNodeValue")

    # Group output interface socket
    has_image_out = any(getattr(s, "name", "") == "Image" and getattr(s, "in_out", "") == "OUTPUT"
                        for s in tree.interface.items_tree)
    if not has_image_out:
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")

    # Inputs
    node_img = nodes.new(type="CompositorNodeImage")
    node_img.location = (-700, 300)
    node_img.label = f"Plate ({img_file.name})"
    img_obj = bpy.data.images.load(str(img_file), check_existing=True)
    img_obj.reload()
    node_img.image = img_obj

    node_norm = nodes.new(type="CompositorNodeImage")
    node_norm.location = (-700, 0)
    node_norm.label = f"Normals ({norm_file.name})"
    norm_obj = bpy.data.images.load(str(norm_file), check_existing=True)
    norm_obj.reload()
    try:
        norm_obj.colorspace_settings.name = "Non-Color"
    except Exception:
        pass
    node_norm.image = norm_obj

    gizmo = nodes.new(type="CompositorNodeNormal")
    gizmo.location = (-400, -120)
    gizmo.label = "Light Direction"

    def math2(op, a_out, b_out, x, y, b_default=None):
        m = make_math()
        m.location = (x, y)
        m.operation = op
        links.new(a_out, m.inputs[0])
        if b_out is not None:
            links.new(b_out, m.inputs[1])
        elif b_default is not None:
            m.inputs[1].default_value = b_default
        return m

    need_remap = norm_file.suffix.lower() not in (".exr",)
    sep_type = "CompositorNodeSeparateColor" if hasattr(bpy.types, "CompositorNodeSeparateColor") else "CompositorNodeSeparateRGBA"
    sepN = nodes.new(type=sep_type)
    sepN.location = (-150, 100)
    links.new(node_norm.outputs[0], sepN.inputs[0])

    sepL = nodes.new(type=sep_type)
    sepL.location = (-150, -150)
    links.new(gizmo.outputs[0], sepL.inputs[0])

    prods = []
    for i, (cname, lx) in enumerate((("R", -50), ("G", -100), ("B", -150))):
        chan = sepN.outputs[i]
        if need_remap:
            chan = math2("SUBTRACT", chan, None, lx, 60, b_default=0.5).outputs[0]
            chan = math2("MULTIPLY", chan, None, lx + 130, 60, b_default=2.0).outputs[0]
        prods.append(math2("MULTIPLY", chan, sepL.outputs[i], 250, 60 - i * 90).outputs[0])

    add_rg = math2("ADD", prods[0], prods[1], 430, 50)
    dot = math2("ADD", add_rg.outputs[0], prods[2], 600, 0)
    diff = math2("MAXIMUM", dot.outputs[0], None, 770, 0, b_default=0.0)

    light_col = nodes.new(type="CompositorNodeRGB")
    light_col.location = (770, 300)
    light_col.label = "Key Light Color"
    light_col.outputs[0].default_value = (1.0, 0.92, 0.78, 1.0)

    light_pwr = make_val()
    light_pwr.location = (770, 150)
    light_pwr.label = "Light Intensity"
    light_pwr.outputs[0].default_value = 1.4

    _, dcol = mix_color("MULTIPLY", diff.outputs[0], light_col.outputs[0], 970, 150, "Diffuse x Color")
    _, dboost = mix_color("MULTIPLY", dcol, light_pwr.outputs[0], 1170, 150, "x Power")

    amb = make_val()
    amb.location = (970, -60)
    amb.label = "Ambient Fill"
    amb.outputs[0].default_value = 0.35

    _, total = mix_color("ADD", dboost, amb.outputs[0], 1370, 100, "Total light")
    _, final = mix_color("MULTIPLY", node_img.outputs[0], total, 1570, 200, "Relit plate")

    comp = nodes.new(type="NodeGroupOutput")
    comp.location = (1820, 200)
    for s in comp.inputs:
        if s.bl_idname == "NodeSocketColor" or s.name == "Image":
            links.new(final, s)
            break

    viewer = nodes.new(type="CompositorNodeViewer")
    viewer.location = (1820, 0)
    links.new(final, viewer.inputs[0])

    return True, "Compositor relighter ready."
