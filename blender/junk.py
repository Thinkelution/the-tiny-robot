"""The Junk Stacks: the yard of crate mountains on Gridhaven's south-west edge where Tiny lives (runs inside Blender).

  import junk
  parts = junk.build(sc, tod="dawn", fog=0.03, skid=False, scraps=False, weed_water=1.0)

Local coordinates: Tiny's crate home sits at the origin with its door and plank porch facing east (+X), into the
morning sun. The cracked slab lane runs east from the porch past the weed (WEED), then bends north-east toward the
one gap in the crate towers, the way to the Old Grove (which is 170 m away to the north-east: city.json puts the
yard at (-118, -124) and the Grove at the city centre). Around the clearing, uneven towers of rust-orange and grey
crates rise 4-18 m, two idle gantry cranes stand in the haze, and the scrap pile with the First Workshop's emblem
plate leans beside Tiny's crate.

All the crates are a handful of merged meshes (one per paint), so 2,000+ crates stay cheap.
"""
import math
import random

import bpy

import plants
import world

HOME = (0.0, 0.0)
WEED = (2.6, 0.45)
GAP = (24.0, 20.0)
GROVE = (118.0, 124.0)
PAINTS = ["#9c5a48", "#b4643a", "#8a5a3c", "#7d8288", "#5f6f78", "#a7a199", "#6b4a3a", "#c27a46"]

_UNIT = None


def _unit():
    """A unit box with a small fixed bevel (crate edges)."""
    global _UNIT
    if _UNIT:
        return _UNIT
    import bmesh
    bm_ = bmesh.new()
    bmesh.ops.create_cube(bm_, size=1.0)
    bmesh.ops.bevel(bm_, geom=list(bm_.edges), offset=0.03, segments=1, affect="EDGES")
    _UNIT = ([tuple(v.co) for v in bm_.verts], [tuple(v.index for v in f.verts) for f in bm_.faces])
    bm_.free()
    return _UNIT


def boxes_mesh(name, coll, mats, boxes):
    """One mesh object from many boxes: boxes = [(centre, size, rot_z, material index)], box UVs at 1 UV = 1 m."""
    uv_, uf = _unit()
    verts, faces, mi = [], [], []
    for (c, sz, rz, m) in boxes:
        cs, sn = math.cos(rz), math.sin(rz)
        base = len(verts)
        for (x, y, z) in uv_:
            x, y, z = x * sz[0], y * sz[1], z * sz[2]
            verts.append((c[0] + x * cs - y * sn, c[1] + x * sn + y * cs, c[2] + z))
        for f in uf:
            faces.append(tuple(base + i for i in f))
            mi.append(m)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", mi)
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
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _crate_mats():
    return [world.mat(f"junk_{c}", "painted_metal", c, wear=0.7, dirt=0.75, rough=0.7, tile=1.5) for c in PAINTS]


def _clear(x, y):
    """The clearing round Tiny's home, the lane east, and the corridor north-east to the gap stay open."""
    if math.hypot(x - 1.5, y) < 9.0:
        return False
    if -2 < x < 14 and abs(y) < 4.0:                          # the lane east
        return False
    # the corridor from the lane's end to the gap and beyond, toward the Grove
    ax, ay, bx, by = 10.0, 0.0, GAP[0] + 30, GAP[1] + 30
    t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    if math.hypot(x - (ax + (bx - ax) * t), y - (ay + (by - ay) * t)) < 5.0:
        return False
    return True


def _towers(coll, rnd):
    mats = _crate_mats()
    boxes = []
    placed = []
    n = 0
    tries = 0
    while n < 95 and tries < 5000:
        tries += 1
        x, y = rnd.uniform(-48, 48), rnd.uniform(-36, 36)
        fw = rnd.uniform(3.0, 6.5)
        if not _clear(x, y) or not all(_clear(x + dx, y + dy) for dx in (-fw / 2, fw / 2) for dy in (-fw / 2, fw / 2)):
            continue
        if any(math.hypot(x - px, y - py) < (fw + pw) / 2 + 0.6 for (px, py, pw) in placed):
            continue
        placed.append((x, y, fw))
        n += 1
        near = math.hypot(x, y)
        h_max = rnd.uniform(4.0, 10.0) if near < 20 else rnd.uniform(7.0, 18.0)
        z = 0.0
        w = fw
        rot = rnd.uniform(-0.15, 0.15)
        while z < h_max and w > 1.0:
            # one layer: a 1-3 x 1-3 grid of crates, each its own size and paint, a little skewed
            k = rnd.choice([1, 2, 2, 3])
            cell = w / k
            layer_h = 0.0
            for i in range(k):
                for j in range(k):
                    if rnd.random() < 0.12 and z > 0:
                        continue                                  # gaps: towers are uneven
                    s = cell * rnd.uniform(0.82, 0.98)
                    sh = s * rnd.uniform(0.7, 1.05)
                    cx = x + (i - (k - 1) / 2) * cell
                    cy = y + (j - (k - 1) / 2) * cell
                    c, sn = math.cos(rot), math.sin(rot)
                    lx, ly = cx - x, cy - y
                    boxes.append(((x + lx * c - ly * sn, y + lx * sn + ly * c, z + sh / 2), (s, s, sh),
                                  rot + rnd.uniform(-0.05, 0.05), rnd.randrange(len(PAINTS))))
                    layer_h = max(layer_h, sh)
            z += layer_h
            w *= rnd.uniform(0.7, 0.95)
            rot += rnd.uniform(-0.12, 0.12)
    boxes_mesh("crate_towers", coll, mats, boxes)
    return placed


def _home(coll, rnd):
    """Tiny's crate: 0.9 m, a square doorway in the east face glowing warm inside, a plank porch, and the small
    leaning stack by the door (S01)."""
    wood = world.mat("tiny_crate", "painted_metal", "#a7a199", wear=0.6, dirt=0.6, tile=1.0)
    plank = world.tex_mat("porch_plank", "bark", "#9a7a58", tile=0.8, rough=0.85)
    s, t = 0.9, 0.05
    x, y = HOME
    world.box(coll, "home_back", (t, s, s), (x - s / 2 + t / 2, y, s / 2), wood, 0.01)
    for sd in (-1, 1):
        world.box(coll, "home_side", (s, t, s), (x, y + sd * (s / 2 - t / 2), s / 2), wood, 0.01)
    world.box(coll, "home_top", (s, s, t), (x, y, s - t / 2), wood, 0.01)
    world.box(coll, "home_floor", (s, s, t), (x, y, t / 2), wood, 0.01)
    # the front with a square doorway 0.42 x 0.42 (Tiny is 0.35)
    d = 0.42
    fx = x + s / 2 - t / 2
    world.box(coll, "home_front", (t, (s - d) / 2, s), (fx, y - (s + d) / 4, s / 2), wood, 0.01)
    world.box(coll, "home_front", (t, (s - d) / 2, s), (fx, y + (s + d) / 4, s / 2), wood, 0.01)
    world.box(coll, "home_lintel", (t, d, s - d - t), (fx, y, d + t + (s - d - t) / 2), wood, 0.01)
    # slats painted on: three thin battens per side
    batten = world.mat("batten", "painted_metal", "#8a8478", wear=0.6, dirt=0.6, tile=1.0)
    for z in (0.2, 0.45, 0.7):
        for sd in (-1, 1):
            world.box(coll, "batten", (s + 0.02, 0.02, 0.06), (x, y + sd * (s / 2 + 0.01), z), batten, 0.005)
    world.box(coll, "porch", (0.55, 0.62, 0.05), (x + s / 2 + 0.27, y, 0.025), plank, 0.005)
    # warm light inside the doorway
    ld = bpy.data.lights.new("home_glow", "POINT")
    ld.energy = 6.0
    ld.color = (1.0, 0.7, 0.4)
    ld.shadow_soft_size = 0.15
    ob = bpy.data.objects.new("home_glow", ld)
    coll.objects.link(ob)
    ob.location = (x + 0.05, y, 0.4)
    world.box(coll, "home_lamp", (0.1, 0.1, 0.06), (x - 0.25, y, s - 0.12), world.emissive("home_lamp", "#ffcf8a", 8), 0.01)
    # the leaning stack beside the door: three small crates, the top one tilting out over the path
    small = world.mat("small_crate", "painted_metal", "#b4643a", wear=0.6, dirt=0.6, tile=1.0)
    bx, by = x + 0.7, y - 0.95
    world.box(coll, "lean_crate", (0.36, 0.36, 0.36), (bx, by, 0.18), small, 0.02, rot=0.1)
    world.box(coll, "lean_crate", (0.33, 0.33, 0.33), (bx + 0.02, by, 0.36 + 0.165), small, 0.02, rot=-0.08)
    top = world.box(coll, "lean_crate", (0.32, 0.32, 0.32), (bx + 0.12, by + 0.05, 0.69 + 0.15), small, 0.02, rot=0.2)
    top.rotation_euler.y = 0.22


def _scrap(coll, rnd, scraps):
    """The scrap pile north of the crate, the First Workshop's emblem plate leaning on it, and (S14) three scrap
    cubes on the porch."""
    metal = world.mat("scrap_metal", "bare_metal", "#7d8288", rough=0.5, dirt=0.7, tile=1.0)
    rust = world.mat("scrap_rust", "painted_metal", "#8a4a32", wear=0.8, dirt=0.8, tile=1.0)
    x, y = HOME[0] + 0.2, HOME[1] + 1.6
    for _ in range(14):
        s = rnd.uniform(0.12, 0.45)
        world.box(coll, "scrap", (s * rnd.uniform(0.6, 1.6), s, s * rnd.uniform(0.4, 1.0)),
                  (x + rnd.uniform(-0.7, 0.7), y + rnd.uniform(-0.4, 0.4), rnd.uniform(0.05, 0.4)),
                  rnd.choice([metal, rust]), 0.01, rot=rnd.uniform(0, 3), shape=rnd.choice(["box", "box", "cylinder_x"]))
    brass = world.mat("emblem_brass", "bare_metal", "#b08a3e", rough=0.45, dirt=0.6, tile=1.0)
    plate = world.box(coll, "emblem_plate", (0.05, 0.62, 0.46), (x + 0.75, y - 0.1, 0.42), brass, 0.01)
    plate.rotation_euler = (0.0, -0.25, 0.25)
    dark = world.mat("emblem_mark", "plastic", "#3a2e1c", wear=0.0, dirt=0.3, rough=0.6)
    # the First Workshop's square emblem: a square ring with a smaller square inside
    for (dy, dz, sy, sz) in ((0, 0.12, 0.26, 0.03), (0, -0.12, 0.26, 0.03), (0.12, 0, 0.03, 0.26), (-0.12, 0, 0.03, 0.26),
                             (0, 0, 0.08, 0.08)):
        m = world.box(coll, "emblem_mark", (0.012, sy, sz), (x + 0.75 + 0.03, y - 0.1 + dy, 0.42 + dz), dark, 0.0)
        m.parent = plate
        m.location = (0.03, dy, dz)
    if scraps:
        for k in range(3):
            world.box(coll, "scrap_cube", (0.09, 0.09, 0.09), (HOME[0] + 0.92, HOME[1] - 0.27 + k * 0.13, 0.095),
                      metal, 0.01, rot=rnd.uniform(-0.2, 0.2))


def _ground(coll, rnd, ctrl, skid):
    slab = world.tex_mat("yard_slab", "concrete", "#8a867e", tile=2.5, rough=0.85)
    dirt = world.tex_mat("yard_dirt", "asphalt", tile=3.0, rough=0.9, bump=0.5)
    world.box(coll, "yard", (400, 400, 0.2), (0, 0, -0.1), dirt, 0)
    # the slab lane: east from the porch, then north-east to the gap
    lane = []
    for k in range(13):
        lane.append(((1.3 + k * 1.02, 0.0, 0.0), (1.0, 2.6, 0.04), 0.0, 0))
    for k in range(34):
        t = k / 33
        lx, ly = 14 + (GAP[0] + 22 - 14) * t, (GAP[1] + 22) * t
        lane.append(((lx, ly, 0.0), (1.0, 2.6, 0.04), math.atan2(GAP[1] + 22, GAP[0] + 8), 0))
    boxes_mesh("lane", coll, [slab], [(c, s, r, m) for (c, s, r, m) in lane])
    # the crack and the weed in it
    crack = world.mat("crack", "plastic", "#1b1c1e", wear=0.0, dirt=0.2, rough=0.9)
    wx, wy = WEED
    for (dx, dy, L, a) in ((0, 0, 0.5, 0.3), (0.28, 0.1, 0.3, -0.4), (-0.25, -0.06, 0.28, 0.7)):
        world.box(coll, "crack", (L, 0.015, 0.006), (wx + dx, wy + dy, 0.021), crack, 0.0, rot=a)
    leaf = plants.leaf_mat("#6fb84e", ctrl)
    stem = world.box(coll, "weed_stem", (0.012, 0.012, 0.11), (wx, wy, 0.075), leaf, 0.003)
    for sd in (-1, 1):
        lf = world.box(coll, "weed_leaf", (0.07, 0.035, 0.008), (wx + sd * 0.035, wy, 0.13), leaf, 0.003)
        lf.rotation_euler = (0, -sd * 0.45, 0.3)
    if skid:
        skid_m = world.mat("skid", "rubber", "#121212", wear=0.0, dirt=0.2, tile=1.0)
        for off in (-0.22, 0.22):
            world.box(coll, "skid", (3.6, 0.13, 0.004), (wx + 0.9, wy + 0.42 + off, 0.022), skid_m, 0.0, rot=0.18)


def _cranes(coll):
    paint = world.mat("crane", "painted_metal", "#c9a23a", wear=0.7, dirt=0.7, tile=2.0)
    dark = world.mat("crane_dark", "painted_metal", "#3c4248", wear=0.5, dirt=0.7, tile=1.0)
    for (cx, cy, rot, h, span) in ((-20.0, 14.0, 0.3, 16.0, 22.0), (30.0, -16.0, -0.5, 13.0, 18.0)):
        c, s = math.cos(rot), math.sin(rot)
        for side in (-1, 1):
            lx, ly = cx + side * span / 2 * c, cy + side * span / 2 * s
            world.box(coll, "crane_leg", (0.8, 0.8, h), (lx, ly, h / 2), paint, 0.05)
            world.box(coll, "crane_foot", (2.4, 1.0, 0.6), (lx, ly, 0.3), dark, 0.04, rot=rot + math.pi / 2)
        world.box(coll, "crane_beam", (span + 1.6, 1.0, 1.2), (cx, cy, h + 0.6), paint, 0.05, rot=rot)
        world.box(coll, "crane_trolley", (1.6, 1.4, 0.9), (cx + 3 * c, cy + 3 * s, h - 0.2), dark, 0.05, rot=rot)
        world.box(coll, "crane_cable", (0.06, 0.06, h * 0.55), (cx + 3 * c, cy + 3 * s, h - 0.6 - h * 0.275), dark, 0.0)
        world.box(coll, "crane_hook", (0.6, 0.4, 0.5), (cx + 3 * c, cy + 3 * s, h * 0.45 - 0.6), dark, 0.05)


def _distance(coll, rnd, grove_water):
    """The city beyond the yard, and the Grove's treetops far off to the north-east."""
    for _ in range(60):
        a, r = rnd.uniform(0, math.tau), rnd.uniform(70, 170)
        x, y = math.cos(a) * r, math.sin(a) * r
        if abs(math.atan2(y - 0, x - 0) - math.atan2(GROVE[1], GROVE[0])) < 0.12 and r < 150:
            continue                                          # keep the line of sight to the Grove clear
        world.tower(coll, rnd, x, y, rnd.uniform(14, 22), rnd.uniform(14, 22), rnd.uniform(20, 56),
                    rnd.choice(world.PALETTE), rnd.choice(["concrete", "corrugated"]))
    ctrl = plants.control(coll, "grove_far_water", grove_water)
    for _ in range(22):
        plants.tree(coll, rnd, GROVE[0] + rnd.uniform(-26, 26), GROVE[1] + rnd.uniform(-26, 26), ctrl,
                    height=rnd.uniform(8, 12), girth=0.6)


def build(sc, tod="dawn", skid=False, scraps=False, weed_water=1.0, grove_water=0.85, seed=41):
    world.CFG = world.TOD[tod]
    world.HAZE = world.CFG["haze"]
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("junk_stacks")
    sc.collection.children.link(coll)
    world.sky(sc)
    ctrl = plants.control(coll, "weed_water", weed_water)
    _ground(coll, rnd, ctrl, skid)
    towers = _towers(coll, rnd)
    _home(coll, rnd)
    _scrap(coll, rnd, scraps)
    _cranes(coll)
    _distance(coll, rnd, grove_water)
    print(f"junk_stacks: {len(towers)} crate towers, tod={tod}")
    return {"coll": coll, "weed": WEED, "home": HOME}
