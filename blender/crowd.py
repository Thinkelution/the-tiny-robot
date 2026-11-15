"""Background robots for Gridhaven's crowds: boxy extras with chest lamps (runs inside Blender).

  import crowd
  crowd.build(coll, rnd, spots, lamps)     # spots = [(x, y, yaw)], lamps = "off" | "green" | "red" | [state per robot]

The whole crowd is ONE mesh with a few material slots (body paints, dark metal, visor glow, and the chest lamp in
off / green / red), so 200+ extras cost about as much as one hero robot. Each extra is a few rounded boxes: legs or
a tread base, a body, a head with a visor, arms, sometimes an antenna, and the chest lamp on its front, which is
what votes. Extras face +X at yaw 0 (the Big Board side of Main Square).
"""
import math

import bpy

import plants
import world

PAINTS = ["#8a9aa6", "#b98e5d", "#9c5a48", "#5f7f86", "#c9b48a", "#6d6f86", "#a7a199", "#7b8f6a", "#c97a4a"]


def _mats():
    m = [world.mat(f"extra_{c}", "painted_metal", c, wear=0.4, dirt=0.5, tile=1.0) for c in PAINTS]
    dark = world.mat("extra_dark", "painted_metal", "#2b2f36", wear=0.3, dirt=0.5, tile=1.0)
    visor = world.emissive("extra_visor", "#9fe8ff", 3.0)
    off = world.mat("lamp_off", "plastic", "#1d2126", wear=0.0, dirt=0.2, rough=0.2)
    green = world.emissive("lamp_green", "#3dff6a", 14.0)
    red = world.emissive("lamp_red", "#ff2a1e", 14.0)
    return m + [dark, visor, off, green, red]


_UNIT = None


def _unit():
    """A unit box with a small bevel: extras read as machined boxes, not pillows."""
    global _UNIT
    if _UNIT:
        return _UNIT
    import bmesh
    bm_ = bmesh.new()
    bmesh.ops.create_cube(bm_, size=1.0)
    bmesh.ops.bevel(bm_, geom=list(bm_.edges), offset=0.08, segments=2, affect="EDGES", profile=0.5)
    _UNIT = ([tuple(v.co) for v in bm_.verts], [tuple(v.index for v in f.verts) for f in bm_.faces])
    bm_.free()
    return _UNIT


def build(coll, rnd, spots, lamps="off", name="crowd"):
    mats = _mats()
    n_paint = len(PAINTS)
    DARK, VISOR, OFF, GREEN, RED = n_paint, n_paint + 1, n_paint + 2, n_paint + 3, n_paint + 4
    uv_, uf = _unit()
    verts, faces, mat_idx = [], [], []

    def cube(cx, cy, cz, sx, sy, sz, mi, ox, oy, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        base = len(verts)
        for (x, y, z) in uv_:
            lx, ly, lz = cx + x * sx, cy + y * sy, cz + z * sz
            verts.append((ox + lx * c - ly * s, oy + lx * s + ly * c, lz))
        for f in uf:
            faces.append(tuple(base + i for i in f))
            mat_idx.append(mi)

    for k, (x, y, yaw) in enumerate(spots):
        state = lamps if isinstance(lamps, str) else lamps[k]
        lamp = {"off": OFF, "green": GREEN, "red": RED}[state]
        kind = rnd.random()
        paint = rnd.randrange(n_paint)
        h = rnd.uniform(1.5, 2.6)
        if kind < 0.25:                       # short and wide, on a tread base
            h *= 0.75
            bw, bd = h * 0.55, h * 0.45
            cube(0, 0, h * 0.09, bd * 1.1, bw * 1.15, h * 0.18, DARK, x, y, yaw)
            body_z0 = h * 0.18
        else:                                 # two sturdy legs on block feet
            bw, bd = h * 0.4, h * 0.3
            leg_h = h * rnd.uniform(0.22, 0.3)
            for side in (-1, 1):
                cube(bd * 0.1, side * bw * 0.25, 0.06, bd * 0.75, bw * 0.36, 0.12, DARK, x, y, yaw)
                cube(0, side * bw * 0.25, leg_h / 2 + 0.06, bd * 0.5, bw * 0.3, leg_h, DARK, x, y, yaw)
            body_z0 = leg_h + 0.06
        body_h = h * rnd.uniform(0.36, 0.44)
        cube(0, 0, body_z0 + body_h / 2, bd, bw, body_h, paint, x, y, yaw)
        # chest lamp on the front (+X) face
        ls = min(bw, body_h) * 0.42
        cube(bd / 2 + 0.01, 0, body_z0 + body_h * 0.6, 0.08, ls, ls, lamp, x, y, yaw)
        if lamp != OFF:                       # a lamp cap on the shoulders, so the vote reads from above too
            cube(0, 0, body_z0 + body_h + 0.01, bd * 0.3, bw * 0.3, 0.04, lamp, x, y, yaw)
        # arms
        for side in (-1, 1):
            cube(0, side * (bw / 2 + bw * 0.1), body_z0 + body_h * 0.55, bd * 0.35, bw * 0.18, body_h * 0.8,
                 paint if rnd.random() < 0.5 else DARK, x, y, yaw)
        # head and visor
        hz = body_z0 + body_h + h * 0.02
        hh = h * rnd.uniform(0.16, 0.22)
        hw = bw * rnd.uniform(0.6, 0.9)
        cube(0, 0, hz + hh / 2, bd * 0.85, hw, hh, paint, x, y, yaw)
        cube(bd * 0.43, 0, hz + hh * 0.55, 0.04, hw * 0.75, hh * 0.28, VISOR, x, y, yaw)
        if rnd.random() < 0.35:
            cube(0, 0, hz + hh + h * 0.05, 0.04, 0.04, h * 0.1, DARK, x, y, yaw)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", mat_idx)
    uv = me.uv_layers.new(name="UVMap")
    co = [0.0] * (len(me.loops) * 2)
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_i, v_i = [(1, 2), (0, 2), (0, 1)][ax]
        for li in poly.loop_indices:
            v = verts[me.loops[li].vertex_index]
            co[li * 2], co[li * 2 + 1] = v[u_i], v[v_i]
    uv.data.foreach_set("uv", co)
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    print(f"crowd: {len(spots)} extras")
    return ob


def spots_in(rnd, x0, x1, y0, y1, n, face_x=1, keep_out=(), spacing=1.25):
    """Loose rows inside a rectangle, all facing roughly toward +X (or -X), clear of keep-out circles."""
    out = []
    tries = 0
    while len(out) < n and tries < n * 60:
        tries += 1
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if any(math.hypot(x - kx, y - ky) < kr for (kx, ky, kr) in keep_out):
            continue
        if any(math.hypot(x - ox, y - oy) < spacing for (ox, oy, _) in out):
            continue
        yaw = (0.0 if face_x > 0 else math.pi) + rnd.uniform(-0.35, 0.35)
        out.append((x, y, yaw))
    return out
