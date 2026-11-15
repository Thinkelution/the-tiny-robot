"""The Rooftop Nursery on top of the old Seed Tower, on the Old Grove's north edge (runs inside Blender).

  import nursery
  parts = nursery.build(sc, tod="afternoon", water=0.1, grove_water=0.85)

The set is the Grove's city (grove.build without its stand-in Seed Tower) plus the tower and its roof:
- the Seed Tower: 20 x 20 m, 24 m tall, old brick red, centred at ORIGIN; roof coordinates below are local to it,
  +Y north, the south roof edge looks straight over the Grove;
- five rows of seedling trays running north-south toward that edge, each tray full of box sprouts. Every tray has
  a "health" value driven from the nursery's water control with a delay by its distance from the tank, so one
  keyframed number makes the green ripple travel down the rows (S06): leaves lift (a shape key) and turn from
  grey-green to bright green (the material reads the tray's health);
- the tall water tank at the north-west, a spout and five square carrying tanks beside the greenhouse frame at the
  north-east (S20), the dry pipe leaving the tank's base over square brackets to the east edge and down the wall
  (S04), the square ladder hatch in the south-west corner, a low kerb so Tiny can sit at the edge, and a ramp of
  stacked slabs up from the lower roof next door (S20).
"""
import math
import random

import bpy

import grove
import plants
import world

ORIGIN = (0.0, grove.WALK_OUT + 10.0, 24.0)
HALF = 10.0
ROWS = [-7.2, -3.6, 0.0, 3.6, 7.2]
ROW_Y0, ROW_Y1 = -8.6, 2.8
TRAY = (0.8, 1.4)
TANK = (-6.0, 6.6)


def _seedling_mat():
    name = "p_seedling"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    import materials
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    h = g.node("ShaderNodeAttribute", _attribute_type="OBJECT", _attribute_name="health").outputs["Fac"]
    ramp = g.node("ShaderNodeValToRGB", Fac=h)
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, materials.hex_rgb("#7d8a6a")
    cr.elements[1].position, cr.elements[1].color = 0.85, materials.hex_rgb("#6fd04e")
    g.set(bsdf.inputs["Base Color"], ramp.outputs["Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    bsdf.inputs["Subsurface Weight"].default_value = 0.3
    bsdf.inputs["Subsurface Radius"].default_value = (0.2, 0.4, 0.1)
    bsdf.inputs["Subsurface Scale"].default_value = 0.01
    return m


def _box_verts(c, s, rz=0.0, tilt=(0.0, 0.0)):
    """8 corners of a box centred at c, size s, turned rz about Z; tilt leans the top by (dx, dy) per metre."""
    out = []
    cs, sn = math.cos(rz), math.sin(rz)
    for z in (-0.5, 0.5):
        for (x, y) in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
            lx, ly, lz = x * s[0], y * s[1], z * s[2]
            k = lz + s[2] / 2
            out.append((c[0] + lx * cs - ly * sn + tilt[0] * k, c[1] + lx * sn + ly * cs + tilt[1] * k, c[2] + lz))
    return out


BOX_F = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]


def _tray_seedlings(coll, rnd, cx, cy, ctrl, delay):
    """One tray's sprouts as one mesh with a "dry" shape key; health drives both the key and the colour."""
    up, dry, faces = [], [], []
    for i in range(2):
        for j in range(5):
            x = cx + (i - 0.5) * 0.34 + rnd.uniform(-0.04, 0.04)
            y = cy + (j - 2) * 0.26 + rnd.uniform(-0.04, 0.04)
            h = rnd.uniform(0.14, 0.22)
            rz = rnd.uniform(0, 3.14)
            lean = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
            # stem
            base = len(up)
            up += _box_verts((x, y, 0.16 + h / 2), (0.022, 0.022, h), rz)
            dry += _box_verts((x, y, 0.16 + h * 0.4), (0.022, 0.022, h * 0.8), rz, (lean[0] * 0.8, lean[1] * 0.8))
            faces += [tuple(base + q for q in f) for f in BOX_F]
            # two slab leaves at the top: angled up when healthy, hanging when dry
            for side in (-1, 1):
                ang = rz + side * 1.5708
                ox, oy = math.cos(ang) * 0.05, math.sin(ang) * 0.05
                base = len(up)
                up += _box_verts((x + ox, y + oy, 0.16 + h + 0.01), (0.1, 0.065, 0.012), ang)
                dx, dy = lean[0] * h * 0.6, lean[1] * h * 0.6
                dry += _box_verts((x + ox * 1.2 + dx, y + oy * 1.2 + dy, 0.16 + h * 0.62), (0.1, 0.065, 0.012), ang,
                                  (math.cos(ang) * 0.0, 0.0))
                faces += [tuple(base + q for q in f) for f in BOX_F]
    me = bpy.data.meshes.new("seedlings")
    me.from_pydata(up, [], faces)
    me.materials.append(_seedling_mat())
    ob = bpy.data.objects.new("seedlings", me)
    coll.objects.link(ob)
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="dry")
    for i, v in enumerate(dry):
        sk.data[i].co = v
    # health: the water value, delayed by this tray's distance from the tank, so a rise ripples down the rows
    ob["health"] = 0.0
    fc = ob.driver_add('["health"]')
    fc.driver.type = "SCRIPTED"
    plants._var(fc.driver, ctrl)
    fc.driver.expression = f"max(0.0, min(1.0, (w * 1.45 - {delay:.3f}) / 0.4))"
    fk = sk.driver_add("value")
    fk.driver.type = "SCRIPTED"
    v = fk.driver.variables.new()
    v.name = "h"
    v.type = "SINGLE_PROP"
    v.targets[0].id_type = "OBJECT"
    v.targets[0].id = ob
    v.targets[0].data_path = '["health"]'
    fk.driver.expression = "1 - h"
    return ob


def _trays(coll, rnd, ctrl):
    tray = world.mat("tray", "plastic", "#3b3f45", wear=0.3, dirt=0.6, rough=0.6, tile=1.0)
    soil = world.tex_mat("tray_soil", "concrete", "#4a3a2c", tile=0.8, rough=0.95)
    n = 0
    tx, ty = TANK
    for x in ROWS:
        y = ROW_Y1 - TRAY[1] / 2
        while y > ROW_Y0:
            world.box(coll, "tray", (TRAY[0], TRAY[1], 0.14), (x, y, 0.07), tray, 0.02)
            world.box(coll, "tray_soil", (TRAY[0] - 0.08, TRAY[1] - 0.08, 0.02), (x, y, 0.145), soil, 0.0)
            d = math.hypot(x - tx, y - ty) / 18.0           # 0 near the tank, about 1 at the far corner
            _tray_seedlings(coll, rnd, x, y, ctrl, d)
            # a thin drip line along the row
            y -= TRAY[1] + 0.12
            n += 1
        drip = world.mat("drip", "plastic", "#1d2126", wear=0.0, dirt=0.3, rough=0.4)
        world.box(coll, "drip", (0.03, ROW_Y1 - ROW_Y0, 0.03), (x + TRAY[0] / 2 + 0.06, (ROW_Y0 + ROW_Y1) / 2, 0.1),
                  drip, 0.0)
    return n


def _roof(coll, rnd):
    roof = world.tex_mat("nursery_roof", "concrete", "#8f8a80", tile=2.5, rough=0.85)
    kerb = world.tex_mat("nursery_kerb", "concrete", "#b5afa5", tile=1.2)
    world.box(coll, "roof_deck", (2 * HALF - 0.02, 2 * HALF - 0.02, 0.1), (0, 0, -0.03), roof, 0)   # 2 cm above the tower top: no z-fighting
    for (cx, cy, sx, sy) in ((0, -HALF + 0.15, 2 * HALF, 0.3), (0, HALF - 0.15, 2 * HALF, 0.3),
                             (-HALF + 0.15, 0, 0.3, 2 * HALF), (HALF - 0.15, 0, 0.3, 2 * HALF)):
        world.box(coll, "kerb", (sx, sy, 0.22), (cx, cy, 0.11), kerb, 0.03)
    # the tank: a cliff of steel on legs, a spout to the carrying tanks, the dry pipe off its base
    steel = world.mat("nursery_tank", "painted_metal", "#5f7f86", wear=0.55, dirt=0.65, tile=2.0)
    pipe = world.mat("nursery_pipe", "painted_metal", "#4f7fa8", wear=0.5, dirt=0.6, tile=1.0)
    brk = world.mat("nursery_bracket", "painted_metal", "#2f353c", wear=0.5, dirt=0.7, tile=1.0)
    tx, ty = TANK
    for (dx, dy) in ((-1.4, -1.4), (1.4, -1.4), (-1.4, 1.4), (1.4, 1.4)):
        world.box(coll, "tank_leg", (0.25, 0.25, 0.8), (tx + dx, ty + dy, 0.4), brk, 0.03)
    world.box(coll, "tank", (4.2, 4.2, 4.6), (tx, ty, 0.8 + 2.3), steel, 0.12, shape="cylinder_z")
    world.box(coll, "tank_lid", (3.0, 3.0, 0.25), (tx, ty, 5.5 + 0.12), steel, 0.08, shape="cylinder_z")
    for z in (1.6, 3.0, 4.4):
        world.box(coll, "tank_band", (4.32, 4.32, 0.12), (tx, ty, z), brk, 0.03, shape="cylinder_z")
    # dry pipe: down from the tank's base, along the roof on square brackets, east to the edge and down the wall
    world.box(coll, "pipe_drop", (0.3, 0.3, 0.7), (tx + 1.6, ty - 1.9, 0.45), pipe, 0.04)
    world.box(coll, "pipe_run", (HALF - (tx + 1.6) + 0.4, 0.3, 0.3), ((tx + 1.6 + HALF + 0.4) / 2, ty - 1.9, 0.15),
              pipe, 0.04)
    for x in range(int(tx) + 3, int(HALF), 2):
        world.box(coll, "pipe_bracket", (0.16, 0.5, 0.36), (x, ty - 1.9, 0.18), brk, 0.02)
    world.box(coll, "pipe_down", (0.3, 0.3, 24.0), (HALF + 0.35, ty - 1.9, -12.0 + 0.15), pipe, 0.04)
    # the spout and the carrying tanks beside the greenhouse
    world.box(coll, "spout", (6.0, 0.22, 0.22), (tx + 4.4, ty + 0.6, 2.2), pipe, 0.03)
    world.box(coll, "spout_down", (0.22, 0.22, 1.0), (tx + 7.3, ty + 0.6, 1.75), pipe, 0.03)
    can = world.mat("carry_tank", "painted_metal", "#c9a24a", wear=0.5, dirt=0.5, tile=1.0)
    for k in range(5):
        world.box(coll, "carry_tank", (0.6, 0.6, 0.6), (tx + 6.4 + (k % 3) * 0.7, ty + 0.4 - (k // 3) * 0.75, 0.3),
                  can, 0.06)
    # the greenhouse frame: square bars, no glass
    bars = world.mat("greenhouse", "painted_metal", "#dfe6e2", wear=0.4, dirt=0.4, tile=1.0)
    gx, gy, gw, gd, gh = 6.2, 6.8, 5.0, 4.0, 2.8
    for (dx, dy) in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1)):
        world.box(coll, "gh_post", (0.1, 0.1, gh), (gx + dx * gw / 2, gy + dy * gd / 2, gh / 2), bars, 0.01)
    for s in (-1, 1):
        world.box(coll, "gh_beam", (gw, 0.1, 0.1), (gx, gy + s * gd / 2, gh), bars, 0.01)
        world.box(coll, "gh_beam", (0.1, gd, 0.1), (gx + s * gw / 2, gy, gh), bars, 0.01)
        world.box(coll, "gh_rafter", (0.1, gd / 2 + 0.3, 0.1), (gx + s * gw / 4, gy, gh + 0.45), bars, 0.01)
    world.box(coll, "gh_ridge", (gw, 0.1, 0.1), (gx, gy, gh + 0.9), bars, 0.01)
    # the square ladder hatch in the south-west corner, lid open
    hatch = world.mat("hatch", "painted_metal", "#7d8288", wear=0.5, dirt=0.6, tile=1.0)
    hx, hy = -8.4, -8.6
    world.box(coll, "hatch_frame", (1.1, 1.1, 0.25), (hx, hy, 0.12), hatch, 0.03)
    lid = world.box(coll, "hatch_lid", (1.0, 0.06, 1.0), (hx, hy + 0.55, 0.65), hatch, 0.02)
    lid.rotation_euler.x = -0.25
    # the ramp of stacked slabs up from the lower roof next door (S20), on the west side
    slab = world.tex_mat("ramp_slab", "concrete", "#a39d92", tile=1.5)
    for k in range(6):
        world.box(coll, "ramp_slab", (1.6, 2.2, 0.5), (-HALF - 0.8 - k * 1.5, -2.0, -k * 0.5 - 0.25), slab, 0.03)
    # the leaf from the Grove that Tiny follows (S04), resting against the first tray
    leaf = world.mat("blown_leaf", "plastic", "#5fa045", wear=0.0, dirt=0.1, tile=1.0)
    world.box(coll, "blown_leaf", (0.12, 0.08, 0.01), (ROWS[0] - TRAY[0] / 2 - 0.08, -7.6, 0.01), leaf, 0.003, rot=0.4)
    # a work lamp on a pole by the greenhouse, lit when the city's lamps are (sunset, night)
    if world.CFG["lamps"] > 0:
        post = world.mat("lamp_post", "painted_metal", "#2f3a40", wear=0.5, dirt=0.5, tile=1.0)
        world.box(coll, "roof_lamp_pole", (0.14, 0.14, 4.2), (3.2, 4.4, 2.1), post, 0.02)
        world.box(coll, "roof_lamp_head", (0.6, 0.4, 0.2), (3.2, 4.0, 4.2), world.emissive("lamp_glow", "#ffcf8a", 14), 0.04)
        ld = bpy.data.lights.new("roof_lamp", "SPOT")
        ld.energy = 1800
        ld.color = (1.0, 0.78, 0.5)
        ld.spot_size = math.radians(110)
        ld.spot_blend = 0.7
        ld.shadow_soft_size = 0.3
        ob = bpy.data.objects.new("roof_lamp", ld)
        coll.objects.link(ob)
        ob.location = (3.2, 3.8, 4.0)
        ob.rotation_euler = (math.radians(28), 0, 0)
    # roof clutter: a vent box and a fan housing
    vent = world.mat("vent", "bare_metal", "#9aa0a6", rough=0.4, dirt=0.5, tile=1.0)
    world.box(coll, "vent", (1.2, 0.8, 0.9), (8.6, -6.0, 0.45), vent, 0.04)
    world.box(coll, "fan", (1.0, 1.0, 0.5), (8.6, -3.4, 0.25), vent, 0.06, shape="cylinder_z")


def _tower(coll):
    """The Seed Tower itself: one old brick-red block (a single tier, so the roof is the full 20 x 20 m)."""
    import facade
    wall = world.tex_mat("seed_tower_wall", "concrete", "#9c5a48", tile=3.0, rough=0.75)
    trim = world.mat("trim", "painted_metal", "#3b3f45", wear=0.4, dirt=0.6, tile=3.0)
    glass, shop = world.glass_mat("glass"), world.glass_mat("shopglass", shop=True)
    me = facade.tier_mesh("seed_tower", 2 * HALF, 2 * HALF, ORIGIN[2], random.Random(31), bay=4.0, storey=3.4,
                          shop=True, balconies=False, style="sparse", parapet=0.0)   # the roof has its own low kerb
    for m in (wall, glass, shop, trim):
        me.materials.append(m)
    ob = bpy.data.objects.new("seed_tower", me)
    coll.objects.link(ob)
    ob.location = (ORIGIN[0], ORIGIN[1], 0)


def build(sc, tod="afternoon", water=0.1, grove_water=0.85, seed=29):
    parts = grove.build(sc, tod=tod, water=grove_water, seed=11, seed_tower=False)
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("rooftop_nursery")
    sc.collection.children.link(coll)
    _tower(coll)
    roof = bpy.data.objects.new("nursery_roof", None)          # everything on the roof is parented here
    coll.objects.link(roof)
    roof.location = ORIGIN
    ctrl = plants.control(coll, "nursery_water", water)
    before = set(bpy.data.objects)
    _roof(coll, rnd)
    n = _trays(coll, rnd, ctrl)
    for ob in set(bpy.data.objects) - before:
        if ob.parent is None:
            ob.parent = roof
    print(f"rooftop_nursery: {n} trays, water={water}, grove water={grove_water}")
    return {"coll": coll, "water": ctrl, "grove": parts}
