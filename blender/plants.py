"""Living plants for Gridhaven: box-trunk trees, saplings and weeds that respond to water (runs inside Blender).

  import plants
  ctrl = plants.control(coll, "grove_water", water=1.0)     # an empty with a "water" property, 0..1, keyframable
  plants.tree(coll, rnd, x, y, ctrl, height=9.0)
  plants.sapling(coll, rnd, x, y, ctrl)
  plants.gauge_mat("grove", ctrl)                             # emissive green / amber / red from the same value

Everything a plant does is driven by the control's "water" value through drivers (Blender's simple expressions, so
no script auto-run is needed):
- leaf colour runs from deep green through olive to dry brown;
- each leaf cluster droops (sinks and tilts outward) and shrinks a little as water drops;
- blossoms (small cubes) open above 0.85;
- every cluster sways on its own phase, more at the top of the tree.
"""
import math

import bpy
from mathutils import Vector

import materials
import robot
import texmat
import world

GREENS = ["#3f7d36", "#4f8f3a", "#5fa045", "#73ad4e", "#4a8a44", "#2f6b33", "#86b552"]
DRY = "#8a7038"
DEAD = "#6b4e2e"


def control(coll, name, water=1.0):
    ob = bpy.data.objects.new(name, None)
    coll.objects.link(ob)
    ob["water"] = float(water)
    ob.id_properties_ui("water").update(min=0.0, max=1.0)
    ob.empty_display_size = 0.5
    return ob


def _var(drv, ctrl, name="w"):
    v = drv.variables.new()
    v.name = name
    v.type = "SINGLE_PROP"
    v.targets[0].id_type = "OBJECT"
    v.targets[0].id = ctrl
    v.targets[0].data_path = '["water"]'
    return v


def _drive(target, path, index, ctrl, expr):
    fc = target.driver_add(path, index) if index is not None else target.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    _var(drv, ctrl)
    drv.expression = expr
    drv.use_self = False
    return fc


def _water_node(g, ctrl):
    """A Value node inside a material that follows the control's water."""
    val = g.node("ShaderNodeValue")
    val.label = "water"
    fc = val.outputs[0].driver_add("default_value")
    fc.driver.type = "SCRIPTED"
    _var(fc.driver, ctrl)
    fc.driver.expression = "w"
    return val.outputs[0]


def leaf_mat(shade, ctrl):
    """Leaf cluster: the leaves photo as detail, tinted; green to olive to brown with water; soft translucency."""
    name = f"p_leaf_{shade}_{ctrl.name}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    co = texmat._uv(g, 0.9)
    col = texmat._img(g, "leaves", "color", co).outputs["Color"]
    det = texmat._detail(g, col, "leaves", 2.2)
    w = _water_node(g, ctrl)
    ramp = g.node("ShaderNodeValToRGB", Fac=w)
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, materials.hex_rgb(DEAD)
    cr.elements[1].position, cr.elements[1].color = 0.75, materials.hex_rgb(shade)
    mid = cr.elements.new(0.35)
    mid.color = materials.hex_rgb(DRY)
    base = texmat._mul(g, ramp.outputs["Color"], det)
    g.set(bsdf.inputs["Base Color"], base)
    g.set(bsdf.inputs["Roughness"], g.math("ADD", 0.45, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, w), 0.35)))
    bsdf.inputs["Subsurface Weight"].default_value = 0.25
    bsdf.inputs["Subsurface Radius"].default_value = (0.25, 0.4, 0.12)
    bsdf.inputs["Subsurface Scale"].default_value = 0.05
    bsdf.inputs["Coat Weight"].default_value = 0.0
    nm = g.node("ShaderNodeNormalMap", Color=texmat._img(g, "leaves", "normal", co, True).outputs["Color"],
                Strength=0.8)
    g.set(bsdf.inputs["Normal"], nm.outputs[0])
    return world._haze(m)


def bark_mat(tint="#7a5a42"):
    return world.tex_mat(f"bark_{tint}", "bark", tint, tile=1.2, rough=0.85, bump=0.9)


def blossom_mat():
    return world.mat("blossom", "plastic", "#f6c6d8", wear=0.0, dirt=0.05, rough=0.4, tile=1.0)


def gauge_mat(name, ctrl):
    """Gauge light: red below 0.3, amber in the middle, green above 0.7, glowing."""
    mname = f"p_gauge_{name}"
    if mname in bpy.data.materials:
        return bpy.data.materials[mname]
    m = bpy.data.materials.new(mname)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    w = _water_node(g, ctrl)
    ramp = g.node("ShaderNodeValToRGB", Fac=w)
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (1.0, 0.08, 0.04, 1)
    cr.elements[1].position, cr.elements[1].color = 0.7, (0.25, 1.0, 0.35, 1)
    amber = cr.elements.new(0.3)
    amber.color = (1.0, 0.45, 0.04, 1)
    g.set(bsdf.inputs["Base Color"], ramp.outputs["Color"])
    g.set(bsdf.inputs["Emission Color"], ramp.outputs["Color"])
    bsdf.inputs["Emission Strength"].default_value = 6.0
    bsdf.inputs["Roughness"].default_value = 0.2
    return m


def _box(coll, name, size, loc, mat, bevel=0.03, shape="box"):
    ob = robot.mesh_box(name, size, shape, coll, mat, bevel, 2)
    ob.location = loc
    return ob


_UNIT = None
_N = [0]


def _uid(name):
    _N[0] += 1
    return f"{name}.{_N[0]:05d}"


def _unit_rounded():
    """A unit rounded cube (bevel baked in), as plain vertex/face lists so clusters can be assembled fast."""
    global _UNIT
    if _UNIT:
        return _UNIT
    import bmesh
    bm_ = bmesh.new()
    bmesh.ops.create_cube(bm_, size=1.0)
    bmesh.ops.bevel(bm_, geom=list(bm_.edges), offset=0.3, segments=2, affect="EDGES", profile=0.6)
    verts = [tuple(v.co) for v in bm_.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm_.faces]
    bm_.free()
    _UNIT = (verts, faces)
    return _UNIT


def _merged(name, coll, mat, cubes, origin, smooth=True):
    """One mesh object from many rounded cubes: cubes = [(centre, (sx, sy, sz), rot_z)] relative to origin.
    Box-projected UVs at 1 UV = 1 m, so textures keep their scale."""
    uv_, uf = _unit_rounded()
    verts, faces = [], []
    for (c, sz, rz) in cubes:
        cs, sn = math.cos(rz), math.sin(rz)
        base = len(verts)
        for (x, y, z) in uv_:
            x, y, z = x * sz[0], y * sz[1], z * sz[2]
            verts.append((c[0] + x * cs - y * sn, c[1] + x * sn + y * cs, c[2] + z))
        faces += [tuple(base + i for i in f) for f in uf]
    me = bpy.data.meshes.new(_uid(name))
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
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
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(_uid(name), me)
    coll.objects.link(ob)
    ob.location = origin
    return ob


def _cluster(coll, rnd, ctrl, pivot, size, outward, height_frac, shade):
    """One leaf cluster: 2-3 stacked rounded cubes in ONE object with its origin at the branch tip; the object
    droops and sways. Blossoms are a second object parented to it."""
    leaf = leaf_mat(shade, ctrl)
    cubes = []
    for k in range(rnd.choice([2, 3, 3])):
        c = size * rnd.uniform(0.7, 1.05) * (1.0 - 0.18 * k)
        a = rnd.uniform(0, 6.28)
        r = 0.0 if k == 0 else size * rnd.uniform(0.3, 0.45)
        cubes.append(((math.cos(a) * r, math.sin(a) * r, k * size * rnd.uniform(0.25, 0.4)),
                      (c, c * rnd.uniform(0.85, 1.0), c * 0.78), rnd.uniform(0, 1.2)))
    tip = _merged("leaves", coll, leaf, cubes, pivot)
    if rnd.random() < 0.55:
        bl = [((rnd.uniform(-0.45, 0.45) * size, rnd.uniform(-0.45, 0.45) * size, rnd.uniform(0.2, 1.0) * size),
               (0.16, 0.16, 0.16), rnd.uniform(0, 1)) for _ in range(rnd.randint(2, 4))]
        b = _merged("blossom", coll, blossom_mat(), bl, (0, 0, 0))
        b.parent = tip
        for i in range(3):
            _drive(b, "scale", i, ctrl, "max(0.0, min(1.0, (w - 0.85) / 0.12))")
    # droop: sink, tilt outward and shrink as the tree dries; sway on its own phase, more near the top
    ox, oy = outward
    droop = size * 0.45
    tilt = 0.45
    ph = rnd.uniform(0, 6.28)
    f = rnd.uniform(0.045, 0.07)
    amp = 0.025 + 0.035 * height_frac
    _drive(tip, "location", 2, ctrl, f"{pivot[2]:.3f} - (1 - w) * {droop:.3f}")
    _drive(tip, "rotation_euler", 0, ctrl, f"-(1 - w) * {tilt * oy:.3f} + sin(frame * {f:.3f} + {ph:.2f}) * {amp:.3f}")
    _drive(tip, "rotation_euler", 1, ctrl, f"(1 - w) * {tilt * ox:.3f} + sin(frame * {f * 0.83:.3f} + {ph * 1.7:.2f}) * {amp:.3f}")
    for i in range(3):
        _drive(tip, "scale", i, ctrl, "0.78 + 0.22 * w")
    return tip


def grass_mat(ctrl):
    """Grass blades: no texture (blades are too thin to show one); green to straw with water, varied per blade."""
    name = f"p_grass_{ctrl.name}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    w = _water_node(g, ctrl)
    ramp = g.node("ShaderNodeValToRGB", Fac=w)
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, materials.hex_rgb("#9a8048")
    cr.elements[1].position, cr.elements[1].color = 0.7, materials.hex_rgb("#6aa448")
    pos = g.node("ShaderNodeTexCoord").outputs["Object"]
    nz = g.node("ShaderNodeTexNoise", Vector=pos, Scale=1.3, Detail=2.0).outputs["Fac"]
    tip = g.node("ShaderNodeSeparateXYZ", Vector=pos).outputs["Z"]
    shade = g.math("ADD", 0.7, g.math("ADD", g.math("MULTIPLY", nz, 0.4), g.math("MULTIPLY", tip, 1.2)))
    g.set(bsdf.inputs["Base Color"], texmat._mul(g, ramp.outputs["Color"], shade))
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Subsurface Weight"].default_value = 0.3
    bsdf.inputs["Subsurface Radius"].default_value = (0.2, 0.4, 0.1)
    bsdf.inputs["Subsurface Scale"].default_value = 0.02
    return world._haze(m)


def tree(coll, rnd, x, y, ctrl, height=9.0, girth=0.55, bark="#7a5a42", shades=None):
    """A box-trunk tree: a tapering trunk, 4-6 angled branches with clusters at the tip and along the way, and a
    full crown on top. Returns the crown height."""
    shades = shades or GREENS
    bm = bark_mat(bark)
    trunk_h = height * 0.52
    segs = 3 if height > 7 else 2
    z, w = 0.0, girth
    for s in range(segs):
        h = trunk_h / segs
        seg = _box(coll, "trunk", (w, w, h + 0.05), (x, y, z + h / 2), bm, w * 0.12)
        seg.rotation_euler.z = rnd.uniform(-0.15, 0.15)
        z += h
        w *= 0.8
    for a in range(4):                                   # root flare
        ang = a * math.pi / 2 + rnd.uniform(-0.3, 0.3)
        fl = _box(coll, "root", (girth * 1.2, girth * 0.42, girth * 0.4),
                  (x + math.cos(ang) * girth * 0.6, y + math.sin(ang) * girth * 0.6, girth * 0.16), bm, 0.05)
        fl.rotation_euler.z = ang
    tips = []
    nb = rnd.randint(4, 6)
    for b in range(nb):
        ang = b * math.tau / nb + rnd.uniform(-0.35, 0.35)
        bz = trunk_h * rnd.uniform(0.5, 0.98)
        L = height * rnd.uniform(0.24, 0.34)
        lift = rnd.uniform(0.35, 0.75)
        dx, dy, dz = math.cos(ang) * math.cos(lift), math.sin(ang) * math.cos(lift), math.sin(lift)
        bw = girth * 0.36
        br = _box(coll, "branch", (L, bw, bw), (x + dx * L / 2, y + dy * L / 2, bz + dz * L / 2), bm, bw * 0.15)
        br.rotation_euler = (0, -lift, ang)
        tips.append(((x + dx * L, y + dy * L, bz + dz * L), (dx, dy), 1.0))
        tips.append(((x + dx * L * 0.55, y + dy * L * 0.55, bz + dz * L * 0.55 + height * 0.05), (dx, dy), 0.75))
    for k in range(rnd.randint(3, 4)):                   # the crown: a big centre and a ring round it
        ang = k * math.tau / 4 + rnd.uniform(-0.5, 0.5)
        r = height * 0.12
        tips.append(((x + math.cos(ang) * r, y + math.sin(ang) * r, trunk_h + height * rnd.uniform(0.12, 0.22)),
                     (math.cos(ang) * 0.5, math.sin(ang) * 0.5), 0.95))
    tips.append(((x, y, trunk_h + height * 0.26), (0.0, 0.0), 1.3))
    for (tip, out, k) in tips:
        size = height * rnd.uniform(0.15, 0.2) * k
        _cluster(coll, rnd, ctrl, tip, size, out, min(1.0, tip[2] / height), rnd.choice(shades))
    return trunk_h + height * 0.45


def bush(coll, rnd, x, y, ctrl, size=1.0):
    """Undergrowth: a low mound of leaf cubes."""
    _cluster(coll, rnd, ctrl, (x, y, size * 0.25), size, (0.0, 0.0), 0.15, rnd.choice(GREENS))


def grass(coll, rnd, ctrl, points, blades=14, name="grass"):
    """Grass tufts as ONE mesh built from plain vertex lists (thousands of thin tapered boxes stay cheap)."""
    verts, faces = [], []
    box_f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    for (px, py, s) in points:
        for _ in range(blades):
            h = rnd.uniform(0.08, 0.26) * s
            w = rnd.uniform(0.012, 0.022) * s
            bx, by = px + rnd.uniform(-0.12, 0.12) * s, py + rnd.uniform(-0.12, 0.12) * s
            lx, ly = rnd.uniform(-0.3, 0.3) * h, rnd.uniform(-0.3, 0.3) * h
            rot = rnd.uniform(0, 3.14)
            c, s_ = math.cos(rot), math.sin(rot)
            base = len(verts)
            for (z, k) in ((0.0, 1.0), (h, 0.25)):                # the blade tapers to a quarter at the tip
                for (u, v) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    x0, y0 = u * w / 2 * k, v * w * 0.2 * k
                    t = z / h
                    verts.append((bx + x0 * c - y0 * s_ + lx * t, by + x0 * s_ + y0 * c + ly * t, z))
            faces += [tuple(base + i for i in f) for f in box_f]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(grass_mat(ctrl))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def sapling(coll, rnd, x, y, ctrl, height=1.1):
    """The small tree at the centre of the Grove: roughly Tiny's equal (Tiny is 0.35 m, the sapling about 1 m)."""
    bm = bark_mat("#8a6a4c")
    _box(coll, "sapling_stem", (0.06, 0.06, height * 0.75), (x, y, height * 0.375), bm, 0.01)
    for k, (ang, z) in enumerate(((0.4, 0.55), (2.6, 0.7), (4.4, 0.62))):
        L = 0.22
        br = _box(coll, "sapling_twig", (L, 0.035, 0.035),
                  (x + math.cos(ang) * L / 2, y + math.sin(ang) * L / 2, height * z + 0.06), bm, 0.006)
        br.rotation_euler = (0, -0.5, ang)
        tip = (x + math.cos(ang) * L, y + math.sin(ang) * L, height * z + 0.12)
        _cluster(coll, rnd, ctrl, tip, 0.2, (math.cos(ang), math.sin(ang)), 0.5, "#6fb84e")
    _cluster(coll, rnd, ctrl, (x, y, height * 0.78), 0.26, (0.0, 0.0), 0.8, "#7cc456")


def weed(coll, rnd, x, y, ctrl):
    """The weed in the pavement crack: a box stem and two slab leaves."""
    leaf = leaf_mat("#6fb84e", ctrl)
    stem = _box(coll, "weed_stem", (0.012, 0.012, 0.09), (x, y, 0.045), leaf, 0.003)
    tip = _cluster(coll, rnd, ctrl, (x, y, 0.08), 0.05, (0.0, 0.0), 0.3, "#6fb84e")
    return stem, tip
