"""Build a boxy robot from a JSON spec (runs inside Blender).

Spec (metres, Z up, the robot faces -Y):
{
  "id": "tiny", "name": "Tiny", "height_m": 0.35, "locomotion": "hop",
  "materials": [{"id": "tiny_shell", "kind": "painted_metal", "color": "#e8b04a", "wear": 0.7, ...}],
  "parts": [
    {"name": "head", "role": "head", "parent": "root", "shape": "box", "size": [0.22, 0.2, 0.19],
     "pivot": [0, 0, 0.12], "offset": [0, 0, 0.1], "material": "tiny_shell", "bevel": 0.018}
  ],
  "face": {"part": "head", "screen": [0.17, 0.11], "at": [0, 0.0], "eye_color": "#7ff0ff",
           "eyes": 2, "eye_size": [0.04, 0.05], "eye_gap": 0.07, "glow": "#0c3040"},
  "details": [{"part": "head", "kind": "bolts", "side": "front"}]
}
- `pivot` is the joint, relative to the parent's joint. `offset` is the box centre relative to its own joint.
- roles the animator drives: body, head, arm_l/arm_r, forearm_l/forearm_r, hand_l/hand_r, leg_l/leg_r,
  foot_l/foot_r, wheel, antenna, tail, extra. Every part gets an empty named "<id>:<name>" at its joint.
- shapes: box, slab, rounded_box, cylinder_x, cylinder_y, cylinder_z.
Each mesh gets box UVs at a constant 1 UV = 1 m texel density, so generated textures map evenly everywhere.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import materials

EYE_POINTS = 48


def _link(obj, coll):
    coll.objects.link(obj)
    return obj


def _box_uv(bm, uv):
    """Planar UV per face along its dominant axis, in metres (1 UV unit = 1 m)."""
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_i, v_i = [(1, 2), (0, 2), (0, 1)][ax]
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (co[u_i], co[v_i])


def mesh_box(name, size, shape="box", coll=None, mat=None, bevel=0.01, segs=3):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    sx, sy, sz = size
    if shape.startswith("cylinder"):
        axis = shape[-1]
        r = (sy if axis == "x" else sx) / 2
        depth = {"x": sx, "y": sy, "z": sz}[axis]
        bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=r, radius2=r, depth=depth)
        if axis == "x":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "Y"))
        elif axis == "y":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "X"))
        if axis != "x" and axis != "y":
            pass
        # elliptical cylinders: scale the cross-section to the box size
        bmesh.ops.scale(bm, vec=(sx / (depth if axis == "x" else 2 * r), sy / (depth if axis == "y" else 2 * r),
                                 sz / (depth if axis == "z" else 2 * r)), verts=bm.verts)
    else:
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    uv = bm.loops.layers.uv.new("UVMap")
    bm.normal_update()
    _box_uv(bm, uv)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    if coll:
        coll.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if shape == "rounded_box":
        bevel = max(bevel, min(size) * 0.22)
        segs = 6
    if bevel > 0:
        m = ob.modifiers.new("bevel", "BEVEL")
        m.width = min(bevel, min(size) * 0.45)
        m.segments = segs
        m.limit_method = "ANGLE"
        m.angle_limit = math.radians(40)
        m.harden_normals = True
        m.miter_outer = "MITER_ARC"
        ob.modifiers.new("wn", "WEIGHTED_NORMAL").keep_sharp = True
    return ob


def _eye_mesh(name, w, h, side):
    """Rounded-rectangle eye in the XZ plane with expression shape keys. side = -1 (robot's right) or +1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    r = min(w, h) * 0.45
    pts = []
    for i in range(EYE_POINTS):
        a = 2 * math.pi * i / EYE_POINTS
        x, z = math.cos(a), math.sin(a)
        # superellipse -> rounded rectangle
        e = 2 / 5
        px = math.copysign(abs(x) ** e, x) * w / 2
        pz = math.copysign(abs(z) ** e, z) * h / 2
        pts.append((px, pz))
    centre = bm.verts.new((0, 0, 0))
    ring = [bm.verts.new((x, 0, z)) for x, z in pts]
    for i in range(EYE_POINTS):
        bm.faces.new((centre, ring[i], ring[(i + 1) % EYE_POINTS]))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.shape_key_add(name="Basis")

    def key(kname, fn):
        k = ob.shape_key_add(name=kname, from_mix=False)
        for v, base in zip(k.data, me.vertices):
            x, _, z = base.co
            nx, nz = fn(x / (w / 2), z / (h / 2))
            v.co = (nx * w / 2, -0.0005, nz * h / 2)

    # inner = toward the face centre; for the robot's right eye (side -1) inner is +x
    def inner(x):
        return x * -side

    key("blink", lambda x, z: (x * 1.05, z * 0.08 - 0.05))
    key("happy", lambda x, z: (x, (0.15 + 0.55 * (1 - x * x)) if z > 0 else (0.15 + 0.55 * (1 - x * x)) - 0.42))
    # sad: the outer half of the top edge droops; angry: the inner top corner is cut down like a frown
    key("sad", lambda x, z: (x, z * 0.85 - (0.45 * (1 - inner(x)) / 2 * z if z > 0 else 0)))
    key("angry", lambda x, z: (x, min(z, 0.65 - 0.8 * (inner(x) + 1) / 2) if z > 0 else z))
    key("wide", lambda x, z: (x * 1.25, z * 1.25))
    key("squint", lambda x, z: (x * 1.05, z * 0.45))
    for kb in ob.data.shape_keys.key_blocks:
        kb.value = 0.0
    ob.data.shape_keys.use_relative = True
    ob.active_shape_key_index = 0
    return ob


def build(spec: dict, coll=None, at=(0, 0, 0)) -> bpy.types.Object:
    rid = spec["id"]
    coll = coll or bpy.context.scene.collection
    # texture detail scales with the character: one repeat per ~45% of its height (clamped)
    tile = min(1.2, max(0.15, spec.get("height_m", 1.0) * 0.45))
    mats = {m["id"]: materials.make({"tex_tile": tile, **m}) for m in spec["materials"]}
    root = bpy.data.objects.new(f"{rid}:root", None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = spec.get("height_m", 1.0) * 0.5
    root.location = at
    _link(root, coll)
    root["robot_id"] = rid
    root["locomotion"] = spec.get("locomotion", "walk")
    root["height_m"] = spec.get("height_m", 1.0)
    joints = {"root": root}
    meshes = {}
    pending = list(spec["parts"])
    guard = 0
    while pending and guard < 500:
        guard += 1
        p = pending.pop(0)
        par = p.get("parent", "root")
        if par not in joints:
            pending.append(p)
            continue
        j = bpy.data.objects.new(f"{rid}:{p['name']}", None)
        j.empty_display_size = 0.05
        _link(j, coll)
        j.parent = joints[par]
        j.location = p.get("pivot", (0, 0, 0))
        j.rotation_euler = [math.radians(a) for a in p.get("rest_rot", (0, 0, 0))]   # resting joint pose
        j["role"] = p.get("role", "extra")
        joints[p["name"]] = j
        m = mesh_box(f"{rid}:{p['name']}.mesh", p["size"], p.get("shape", "box"), coll,
                     mats.get(p.get("material")), p.get("bevel", 0.01))
        m.parent = j
        m.location = p.get("offset", (0, 0, 0))
        m.rotation_euler = [math.radians(a) for a in p.get("rotate", (0, 0, 0))]
        meshes[p["name"]] = (m, p)
    if pending:
        raise ValueError(f"{rid}: parts with unknown parents: {[p['name'] for p in pending]}")

    face = spec.get("face")
    if face:
        host, hp = meshes[face["part"]]
        sx, sy, sz = hp["size"]
        front = -sy / 2
        sw, sh = face.get("screen", (sx * 0.75, sz * 0.55))
        fx, fz = face.get("at", (0, 0))
        scr_mat = materials.make({"id": f"{rid}_screen", "kind": "screen", "glow": face.get("glow", "#0b2a36"),
                                  "tex_tile": tile})
        depth = min(0.012, sy * 0.06)
        scr = mesh_box(f"{rid}:screen", (sw, depth, sh), "box", coll, scr_mat, min(sw, sh) * 0.12, 4)
        scr.parent = host
        scr.location = (fx, front - depth * 0.35, fz)
        eye_mat = materials.make({"id": f"{rid}_eye", "kind": "emissive", "color": face.get("eye_color", "#7ff0ff"),
                                  "emission": face.get("eye_glow", 2.0)})
        n = face.get("eyes", 2)
        ew, eh = face.get("eye_size", (sw * 0.22, sh * 0.5))
        gap = face.get("eye_gap", sw * 0.42)
        # eyes must sit inside the screen with a margin
        eh = min(eh, sh * 0.78)
        if n == 1:
            ew = min(ew, sw * 0.86)
        else:
            gap = min(gap, sw * 0.5)
            ew = min(ew, (sw * 0.92 - gap), gap * 0.9)
        eyes_root = bpy.data.objects.new(f"{rid}:eyes", None)
        eyes_root.empty_display_size = 0.02
        _link(eyes_root, coll)
        eyes_root.parent = scr
        eyes_root.location = (0, -depth / 2 - 0.0015, 0)
        eyes_root["role"] = "eyes"
        xs = [0.0] if n == 1 else [-gap / 2, gap / 2]
        for k, x in enumerate(xs):
            side = 0 if n == 1 else (-1 if k == 0 else 1)
            e = _eye_mesh(f"{rid}:eye{k}", ew, eh, side or 1)
            e.data.materials.append(eye_mat)
            _link(e, coll)
            e.parent = eyes_root
            e.location = (x, 0, 0)
            e["role"] = "eye"
            for kname, val in (face.get("rest") or {}).items():   # resting expression, e.g. {"squint": 0.4}
                kb = e.data.shape_keys.key_blocks.get(kname)
                if kb:
                    kb.value = val

    for d in spec.get("details", []):
        _detail(rid, d, meshes, coll, mats)
    root["parts"] = list(joints.keys())
    return root


def _side_frame(size, side):
    """centre offset, face normal, and the two in-face axes with their half sizes for a box side."""
    sx, sy, sz = size
    return {
        "front": (Vector((0, -sy / 2, 0)), Vector((0, -1, 0)), (Vector((1, 0, 0)), sx / 2), (Vector((0, 0, 1)), sz / 2)),
        "back": (Vector((0, sy / 2, 0)), Vector((0, 1, 0)), (Vector((1, 0, 0)), sx / 2), (Vector((0, 0, 1)), sz / 2)),
        "left": (Vector((sx / 2, 0, 0)), Vector((1, 0, 0)), (Vector((0, 1, 0)), sy / 2), (Vector((0, 0, 1)), sz / 2)),
        "right": (Vector((-sx / 2, 0, 0)), Vector((-1, 0, 0)), (Vector((0, 1, 0)), sy / 2), (Vector((0, 0, 1)), sz / 2)),
        "top": (Vector((0, 0, sz / 2)), Vector((0, 0, 1)), (Vector((1, 0, 0)), sx / 2), (Vector((0, 1, 0)), sy / 2)),
    }[side]


def _detail(rid, d, meshes, coll, mats):
    host, hp = meshes[d["part"]]
    size = hp["size"]
    side = d.get("side", "front")
    c, n, (ua, uh), (va, vh) = _side_frame(size, side)
    trim = materials.make({"id": "trim_dark_metal", "kind": "bare_metal", "color": "#3a3c40", "roughness": 0.35})
    k = d["kind"]
    s = min(uh, vh)
    made = []
    if k == "bolts":
        r = max(0.004, s * 0.05)
        for du in (-1, 1):
            for dv in (-1, 1):
                b = mesh_box(f"{rid}:bolt", (r * 2, r * 2, r * 2), "cylinder_y" if side in ("front", "back") else
                             ("cylinder_x" if side in ("left", "right") else "cylinder_z"), coll, trim, r * 0.3, 2)
                b.location = c + n * (r * 0.4) + ua * du * (uh * 0.72) + va * dv * (vh * 0.72)
                made.append(b)
    elif k == "vent":
        count = d.get("count", 4)
        w, h = uh * 1.1, vh * 0.7
        for i in range(count):
            t = (i - (count - 1) / 2) * (h / count)
            slat_size = [0, 0, 0]
            for ax_vec, length in ((ua, w), (va, h / count * 0.45), (n, 0.006)):
                for j in range(3):
                    if abs(ax_vec[j]) > 0.5:
                        slat_size[j] = length
            b = mesh_box(f"{rid}:vent", slat_size, "box", coll, trim, 0.0015, 2)
            b.location = c + n * 0.002 + va * t + va * d.get("v", 0) * vh + ua * d.get("u", 0) * uh
            made.append(b)
    elif k in ("panel", "light", "badge"):
        pu, pv = d.get("w", 0.5), d.get("h", 0.5)
        sz = [0, 0, 0]
        for ax_vec, length in ((ua, uh * 2 * pu), (va, vh * 2 * pv), (n, 0.006 if k == "panel" else 0.012)):
            for j in range(3):
                if abs(ax_vec[j]) > 0.5:
                    sz[j] = length
        mat = mats.get(d.get("material")) or (
            materials.make({"id": f"{rid}_light_{d.get('color', '#ff5030')}", "kind": "emissive",
                            "color": d.get("color", "#ff5030"), "emission": 8}) if k == "light" else
            mesh_mat(host))
        b = mesh_box(f"{rid}:{k}", sz, "box", coll, mat, min(x for x in sz if x > 0) * 0.3, 2)
        b.location = c + n * (sz[[abs(n[j]) > 0.5 for j in range(3)].index(True)] / 2 - 0.001) + \
            ua * d.get("u", 0) * uh + va * d.get("v", 0) * vh
        made.append(b)
    elif k == "antenna":
        L = d.get("length", s * 2.5)
        rod = mesh_box(f"{rid}:antenna", (0.008, 0.008, L), "cylinder_z", coll, trim, 0.002, 2)
        rod.location = c + Vector((0, 0, L / 2)) + ua * d.get("u", 0) * uh + va * d.get("v", 0) * vh
        tip_mat = materials.make({"id": f"{rid}_light_{d.get('color', '#ff5030')}", "kind": "emissive",
                                  "color": d.get("color", "#ff5030"), "emission": 8})
        tip = mesh_box(f"{rid}:antenna_tip", (0.022, 0.022, 0.022), "rounded_box", coll, tip_mat, 0.008)
        tip.location = rod.location + Vector((0, 0, L / 2 + 0.01))
        made += [rod, tip]
    for b in made:
        b.parent = host


def mesh_mat(ob):
    return ob.data.materials[0] if ob.data.materials else None


def bounds(root):
    """World-space bounding box of everything under a robot root."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in root.children_recursive:
        if ob.type != "MESH":
            continue
        for c in ob.evaluated_get(dg).bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi
