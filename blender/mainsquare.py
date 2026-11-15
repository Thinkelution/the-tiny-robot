"""Main Square and the Big Board (runs inside Blender).

  import mainsquare
  parts = mainsquare.build(sc, tod="day", lamps="off", board="fastlane", grove_water=0.85, crowd_n=200)

Layout (local coordinates; the square is centred on the origin, +X is east). From world/city.json the square sits
118 m east of the Old Grove at the end of Grove Boulevard, so the Grove's treetops close the view west down the
boulevard. The Big Board towers on the east side above a stage of stacked platforms, each one low enough for Tiny to
hop (0.3 m). The Fast Lane model table stands in front of the stage. The Count House is the tall narrow archive on
the north side. A crate stack at the back of the crowd is Tiny's lookout (S09).
"""
import math
import random
from pathlib import Path

import bpy

import crowd
import plants
import world

ROOT = Path(__file__).resolve().parent.parent
TEX = ROOT / "films" / "the-tiny-robot" / "world" / "textures"

PX, PY = 22.0, 20.0             # plaza half sizes
ROAD = 10.0
WALK = 4.0
FRONT_X, FRONT_Y = PX + ROAD + WALK, PY + ROAD + WALK
BLVD = 10.0                     # Grove Boulevard half width (west, along -X)
GROVE_X = -118.0
STEP = 0.3                      # stage step height: one Tiny hop
STAGE = [(12.0 + k * 1.3, 16.0 - k * 1.6) for k in range(6)]     # (front x, width) per tier; top = 1.8 m
STAGE_TOP = STEP * len(STAGE)
BOARD_X = 24.5


def board_mat(picture, strength):
    name = f"board_{picture}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(TEX / f"board_{picture}.png"), check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["UV"], tex.inputs["Vector"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _screen(coll, picture, strength):
    """The Big Board picture: a plane facing -X with its UVs mapping the whole image."""
    w, h, z0 = 18.0, 10.125, 5.2
    me = bpy.data.meshes.new("board_screen")
    x = BOARD_X - 0.55
    me.from_pydata([(x, w / 2, z0), (x, -w / 2, z0), (x, -w / 2, z0 + h), (x, w / 2, z0 + h)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
    me.materials.append(board_mat(picture, strength) if picture != "off" else
                        world.mat("board_off", "plastic", "#15181d", wear=0.0, dirt=0.2, rough=0.15))
    ob = bpy.data.objects.new("board_screen", me)
    coll.objects.link(ob)
    return ob


def _plaza(coll, rnd):
    slab = world.tex_mat("slab", "concrete", "#8a867e", tile=2.5, rough=0.8)
    slab2 = world.tex_mat("slab2", "concrete", "#7a766f", tile=2.5, rough=0.8)
    kerb = world.tex_mat("kerb", "concrete", "#b5afa5", tile=1.5)
    asphalt = world.tex_mat("asphalt", "asphalt", tile=3.0, rough=0.85, bump=0.5)
    walk = world.tex_mat("sidewalk", "concrete", "#8d8a84", tile=2.0, rough=0.8)
    paint = world.mat("road_paint", "plastic", "#e8e4d8", wear=0.5, dirt=0.4, rough=0.7, tile=1.0)
    world.box(coll, "road", (600, 600, 0.2), (0, 0, -0.25), asphalt, 0)
    # slabs: two shades, merged per shade so 300 slabs stay two objects
    a, b = [], []
    for i in range(int(-PX), int(PX), 3):
        for j in range(int(-PY), int(PY), 3):
            (a if (i * 7 + j * 3) % 5 else b).append(((i + 1.5, j + 1.5, -0.075), (2.94, 2.94, 0.15), 0.0))
    plants._merged("slabs_a", coll, slab, a, (0, 0, 0), smooth=False)
    plants._merged("slabs_b", coll, slab2, b, (0, 0, 0), smooth=False)
    for (cx, cy, sx, sy) in ((0, -PY, 2 * PX + 0.4, 0.4), (0, PY, 2 * PX + 0.4, 0.4),
                             (-PX, 0, 0.4, 2 * PY), (PX, 0, 0.4, 2 * PY)):
        world.box(coll, "kerb", (sx, sy, 0.2), (cx, cy, -0.05), kerb, 0.04)
    # sidewalks round the ring road
    for s in (-1, 1):
        world.box(coll, "walk", (2 * FRONT_X, WALK, 0.15), (0, s * (FRONT_Y - WALK / 2), -0.075), walk, 0.02)
        world.box(coll, "walk", (WALK, 2 * FRONT_Y, 0.15), (s * (FRONT_X - WALK / 2), 0, -0.075), walk, 0.02)
    mid_x, mid_y = PX + ROAD / 2, PY + ROAD / 2
    for v in range(-40, 41, 4):
        for s in (-1, 1):
            world.box(coll, "dash", (2.0, 0.16, 0.02), (v, s * mid_y, -0.14), paint, 0)
            world.box(coll, "dash", (0.16, 2.0, 0.02), (s * mid_x, v, -0.14), paint, 0)


def _stage(coll):
    deck = world.tex_mat("stage", "concrete", "#4a4f57", tile=2.0, rough=0.7)
    edge = world.mat("stage_edge", "painted_metal", "#e8b62a", wear=0.4, dirt=0.4, tile=1.0)
    for k, (fx, w) in enumerate(STAGE):
        depth = (BOARD_X - 1.0) - fx
        z = STEP * (k + 1)
        world.box(coll, "stage", (depth, w, STEP), (fx + depth / 2, 0, z - STEP / 2), deck, 0.03)
        world.box(coll, "stage_edge", (0.12, w, 0.05), (fx + 0.06, 0, z + 0.01), edge, 0.01)
    # the board: a frame on two pillars rising from behind the stage
    frame = world.mat("board_frame", "painted_metal", "#2a2f36", wear=0.3, dirt=0.4, tile=2.0)
    world.box(coll, "board_back", (1.0, 19.6, 11.6), (BOARD_X, 0, 5.2 + 5.06), frame, 0.1)
    for s in (-1, 1):
        world.box(coll, "board_pillar", (1.6, 1.6, 16.5), (BOARD_X + 0.4, s * 9.0, 8.25), frame, 0.1)
    # Shine's hover spot: a glowing ring on the top platform
    ring = world.emissive("hover_ring", "#62f0ff", 4.0)
    top_x = (STAGE[-1][0] + BOARD_X - 1.0) / 2
    for k in range(16):
        a = k * math.tau / 16
        world.box(coll, "hover_ring", (0.35, 0.08, 0.02), (top_x + math.cos(a) * 1.1, math.sin(a) * 1.1,
                                                          STAGE_TOP + 0.01), ring, 0.0, rot=a + math.pi / 2)
    return top_x


def _model_table(coll, rnd):
    """The Fast Lane model: a long grey strip with a bend around a cluster of tiny green cubes."""
    top = world.tex_mat("table", "concrete", "#9a958a", tile=1.5)
    leg = world.mat("table_leg", "painted_metal", "#3c4248", wear=0.4, dirt=0.5, tile=1.0)
    tx = 6.5
    world.box(coll, "model_table", (2.4, 5.0, 0.15), (tx, 0, 0.9), top, 0.03)
    for (dx, dy) in ((-1.0, -2.2), (1.0, -2.2), (-1.0, 2.2), (1.0, 2.2)):
        world.box(coll, "table_leg", (0.15, 0.15, 0.85), (tx + dx, dy, 0.42), leg, 0.02)
    road = world.mat("model_road", "plastic", "#c9ccd2", wear=0.1, dirt=0.2, tile=1.0)
    world.box(coll, "model_road", (0.35, 3.2, 0.04), (tx, -0.6, 1.0), road, 0.01)
    for (dy, dx, a) in ((1.05, 0.25, 0.6), (1.45, 0.42, 0.0), (1.85, 0.25, -0.6)):
        world.box(coll, "model_bend", (0.35, 0.55, 0.04), (tx + dx, dy, 1.0), road, 0.01, rot=a)
    leaf = world.mat("model_tree", "plastic", "#4fb05a", wear=0.0, dirt=0.1, tile=1.0)
    for _ in range(7):
        world.box(coll, "model_tree", (0.14, 0.14, 0.14), (tx + rnd.uniform(-0.25, 0.1), 1.45 + rnd.uniform(-0.25, 0.25),
                                                            1.06), leaf, 0.03)


def _crates(coll):
    """Tiny's lookout at the back of the crowd: a stack it can hop up, one block at a time (0.3-0.4 m steps)."""
    wood = world.mat("crate_q", "painted_metal", "#8a5a3c", wear=0.6, dirt=0.6, tile=1.2)
    x, y = -17.5, -9.0
    for (dx, dy, s, z) in ((0, 0, 0.8, 0), (0.8, 0, 0.8, 0), (0.8, 0.85, 0.8, 0), (0.8, 0, 0.75, 0.8),
                           (0.8, 0.85, 0.7, 0.8), (0.8, 0.4, 0.6, 1.55)):
        world.box(coll, "crate", (s, s, s), (x + dx, y + dy, z + s / 2), wood, 0.04)
    return (x + 0.8, y + 0.4, 2.15)


def _count_house(coll):
    """The Count House: a tall narrow archive on the north side with amber slit windows."""
    rnd = random.Random(21)
    y0 = FRONT_Y
    world.tower(coll, rnd, 0, y0 + 8, 26, 16, 30, "#6d6f86", "concrete")
    amber = world.emissive("archive_slit", "#ffb347", 3.5)
    for k in range(-5, 6):
        world.box(coll, "slit", (0.7, 0.12, 9.0), (k * 2.2, y0 - 0.05, 12.0), amber, 0.0)
    door = world.emissive("archive_door", "#ffcf8a", 2.0)
    world.box(coll, "archive_door", (3.0, 0.12, 3.6), (0, y0 - 0.06, 1.8), door, 0.0)


def _city(coll, rnd):
    lots = []
    for side in ("n", "s", "e"):
        u = -60.0
        while u < 60:
            w, d = rnd.uniform(11, 16), rnd.uniform(12, 18)
            c = u + w / 2
            u += w + rnd.uniform(3.0, 5.0)
            if side == "n":
                if abs(c) < 15:
                    continue                              # the Count House
                lots.append((c, FRONT_Y + d / 2, w, d))
            elif side == "s":
                lots.append((c, -FRONT_Y - d / 2, w, d))
            else:
                lots.append((FRONT_X + d / 2, c, d, w))
    # west side: buildings either side of Grove Boulevard, all the way to the Grove
    x = -FRONT_X
    while x > GROVE_X + 46:
        w = rnd.uniform(12, 16)
        for s in (-1, 1):
            lots.append((x - w / 2, s * (BLVD + WALK + 8), w, 16))
        x -= w + rnd.uniform(3, 5)
    for _ in range(60):
        a, r = rnd.uniform(0, math.tau), rnd.uniform(85, 170)
        x, y = math.cos(a) * r, math.sin(a) * r
        if x < 0 and abs(y) < 30:
            continue                                      # keep the boulevard view clear
        lots.append((x, y, rnd.uniform(14, 22), rnd.uniform(14, 22)))
    for (x, y, w, d) in lots:
        far = math.hypot(x, y) > 80
        h = rnd.uniform(16, 38) if not far else rnd.uniform(30, 64)
        world.tower(coll, rnd, x, y, w, d, h, rnd.choice(world.PALETTE), rnd.choice(["concrete", "concrete", "corrugated"]))
    # lamps: round the plaza and down the boulevard
    for (x, y, r) in ((-14, -PY - 1.0, math.pi / 2), (0, -PY - 1.0, math.pi / 2), (14, -PY - 1.0, math.pi / 2),
                      (-14, PY + 1.0, -math.pi / 2), (14, PY + 1.0, -math.pi / 2)):
        world.lamp(coll, x, y, r)
    for x in range(int(-FRONT_X) - 6, int(GROVE_X) + 40, -14):
        for s in (-1, 1):
            world.lamp(coll, x, s * (BLVD - 1.5), -s * math.pi / 2)


def _grove_far(coll, rnd, water):
    """The Old Grove at the end of the boulevard: trees only, seen over its wall."""
    ctrl = plants.control(coll, "grove_far_water", water)
    stone = world.tex_mat("grove_wall", "concrete", "#b2a892", tile=1.6, rough=0.85)
    world.box(coll, "grove_wall_far", (0.5, 64, 0.75), (GROVE_X + 32, 0, 0.375), stone, 0.04)
    for _ in range(26):
        x, y = GROVE_X + rnd.uniform(-28, 28), rnd.uniform(-28, 28)
        h = rnd.uniform(7, 12)
        plants.tree(coll, rnd, x, y, ctrl, height=h, girth=rnd.uniform(0.45, 0.7))
    return ctrl


def build(sc, tod="day", lamps="off", board="fastlane", grove_water=0.85, crowd_n=200, seed=17, wave=None):
    world.CFG = world.TOD[tod]
    world.HAZE = world.CFG["haze"]
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("main_square")
    sc.collection.children.link(coll)
    world.sky(sc)
    _plaza(coll, rnd)
    top_x = _stage(coll)
    _screen(coll, board, 2.2 if world.CFG["sun"][0] > 2 else 4.5)
    _model_table(coll, rnd)
    lookout = _crates(coll)
    _count_house(coll)
    _city(coll, rnd)
    gctrl = _grove_far(coll, rnd, grove_water)
    keep = [(6.5, 0, 3.4), (-17.1, -8.6, 1.8), (2.0, -5.0, 2.6)]          # table, crates, Quota's gap
    spots = crowd.spots_in(rnd, -19.0, 9.5, -17.5, 17.5, crowd_n, keep_out=keep)
    if lamps in ("mixed", "wave"):
        states = []
        for (x, y, _) in spots:
            if lamps == "mixed":
                states.append("green" if rnd.random() < 0.51 else "red")
            else:                      # a red wave sweeping from the back toward the stage
                front = wave if wave is not None else 0.0
                states.append("red" if x < front + rnd.uniform(-2.0, 2.0) else "off")
        lamps = states
    crowd.build(coll, rnd, spots, lamps)
    print(f"main_square: tod={tod}, board={board}, crowd={len(spots)}")
    return {"coll": coll, "stage_top": (top_x, 0.0, STAGE_TOP), "lookout": lookout, "grove_water": gctrl}
