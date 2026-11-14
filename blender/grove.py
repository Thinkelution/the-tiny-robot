"""The Old Grove set: the last living trees in the middle of Gridhaven (runs inside Blender).

  import grove; parts = grove.build(sc, tod="morning", water=1.0, seed=11)

Layout from films/the-tiny-robot/world/city.json: a 64 m square clearing centred on the origin behind a low kerb
wall with four gates. Mossback's loop is a worn ring 44 m across. The central sapling stands in a small clearing.
The water line runs under grates from the north-east corner (towards the Pipeworks) to the centre, and the great
old tree's root arches across that line. Around the wall: a ring road, sidewalks and the city: the Seed Tower to
the north (the Rooftop Nursery on top), the Pipeworks block to the north-east, Grove Boulevard leaving east to Main
Square, and the end of Quota's raised Fast Lane to the west.

Every plant, and every gauge on the grates, follows one control: parts["water"]["water"] (0 = dead, 1 = thriving).
"""
import math
import random

import bpy

import plants
import world

HALF = 32.0                 # the clearing: |x|, |y| < 32
LOOP_R = 22.0               # Mossback's loop radius
SAPLING = (0.0, 0.0)
GREAT_TREE = (15.0, 19.0)
PIPE_LINE = [(30.0, 30.0), (0.6, 0.6)]      # water line from the north-east corner to the sapling
ROAD_IN, ROAD_OUT = HALF + 0.6, HALF + 10.6
WALK_OUT = ROAD_OUT + 4.0


def _on_line(x, y, pad):
    (ax, ay), (bx, by) = PIPE_LINE
    t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    px, py = ax + (bx - ax) * t, ay + (by - ay) * t
    return math.hypot(x - px, y - py) < pad


def _ground(coll, rnd, ctrl):
    # soil and moss over the whole clearing, a leafy ground cover in patches, the worn loop path
    turf = plants.turf_mat(ctrl)
    moss = plants.leaf_mat("#3f7232", ctrl)
    path = world.tex_mat("loop_path", "concrete", "#a08c6a", tile=2.0, rough=0.95, bump=0.3)
    world.box(coll, "grove_turf", (2 * HALF, 2 * HALF, 0.2), (0, 0, -0.1), turf, 0)
    # ground cover: low flat slabs of leaves, kept off the path ring and the sapling clearing
    cover = []
    for _ in range(120):
        x, y = rnd.uniform(-HALF + 1.5, HALF - 1.5), rnd.uniform(-HALF + 1.5, HALF - 1.5)
        r = math.hypot(x, y)
        if abs(r - LOOP_R) < 2.2 or r < 4.5:
            continue
        s = rnd.uniform(1.2, 3.2)
        cover.append(((x, y, 0.03), (s, s * rnd.uniform(0.6, 1.0), 0.12), rnd.uniform(0, 1.6)))
    # (flat ground-cover slabs read as puddles from low angles; the turf's soil patches do this job now)
    # the loop: segments of a worn ring, slightly sunk
    n = 72
    for k in range(n):
        a = k * math.tau / n
        world.box(coll, "loop", (2 * math.pi * LOOP_R / n + 0.08, 1.9, 0.06),
                  (math.cos(a) * LOOP_R, math.sin(a) * LOOP_R, 0.0), path, 0.01, rot=a + math.pi / 2)
    # fallen slab leaves, more of them when dry (static here; S07 frames set the count with the water value)
    dry = plants.leaf_mat(plants.DRY, ctrl)
    fallen = []
    for _ in range(420):
        x, y = rnd.uniform(-HALF + 1, HALF - 1), rnd.uniform(-HALF + 1, HALF - 1)
        s = rnd.uniform(0.12, 0.26)
        fallen.append(((x, y, 0.035), (s, s * 0.7, 0.015), rnd.uniform(0, 3.1)))
    plants._merged("fallen_leaves", coll, dry, fallen, (0, 0, 0), smooth=False)


def _wall(coll):
    """A low kerb wall round the clearing with a gate in the middle of each side."""
    stone = world.tex_mat("grove_wall", "concrete", "#b2a892", tile=1.6, rough=0.85)
    cap = world.tex_mat("grove_wall_cap", "concrete", "#cfc6b2", tile=1.2, rough=0.8)
    gate = 4.0
    for side in range(4):
        for half in (-1, 1):
            L = HALF - gate / 2
            c = half * (gate / 2 + L / 2)
            if side in (0, 1):              # north / south walls run along x
                y = HALF if side == 0 else -HALF
                world.box(coll, "wall", (L, 0.5, 0.75), (c, y, 0.375), stone, 0.04)
                world.box(coll, "wall_cap", (L + 0.1, 0.62, 0.1), (c, y, 0.8), cap, 0.03)
            else:
                x = HALF if side == 2 else -HALF
                world.box(coll, "wall", (0.5, L, 0.75), (x, c, 0.375), stone, 0.04)
                world.box(coll, "wall_cap", (0.62, L + 0.1, 0.1), (x, c, 0.8), cap, 0.03)
    # gate posts
    for (x, y) in ((g * gate / 2, s * HALF) for g in (-1, 1) for s in (-1, 1)):
        world.box(coll, "gate_post", (0.7, 0.7, 1.3), (x, y, 0.65), cap, 0.06)
    for (x, y) in ((s * HALF, g * gate / 2) for g in (-1, 1) for s in (-1, 1)):
        world.box(coll, "gate_post", (0.7, 0.7, 1.3), (x, y, 0.65), cap, 0.06)


def _water_line(coll, ctrl):
    """Square grates along the buried line, each with a small gauge light in its corner."""
    grate = world.mat("grate", "painted_metal", "#3c4248", wear=0.5, dirt=0.7, tile=1.0)
    frame = world.tex_mat("grate_frame", "concrete", "#9a958a", tile=1.0)
    gauge = plants.gauge_mat("grove", ctrl)
    (ax, ay), (bx, by) = PIPE_LINE
    n = 7
    for k in range(n):
        t = k / (n - 1)
        x, y = ax + (bx - ax) * t * 0.9, ay + (by - ay) * t * 0.9
        world.box(coll, "grate_frame", (1.0, 1.0, 0.1), (x, y, 0.04), frame, 0.02, rot=math.pi / 4)
        for i in range(4):
            off = (i - 1.5) * 0.17
            world.box(coll, "grate_bar", (0.7, 0.06, 0.04), (x + off * 0.707, y - off * 0.707, 0.1), grate, 0.01,
                      rot=math.pi / 4)
        world.box(coll, "gauge_post", (0.1, 0.1, 0.42), (x + 0.42, y, 0.21), grate, 0.02)
        world.box(coll, "gauge_head", (0.24, 0.24, 0.12), (x + 0.42, y, 0.46), grate, 0.03)
        world.box(coll, "gauge_lamp", (0.16, 0.16, 0.05), (x + 0.42, y, 0.53), gauge, 0.02)


def _crew_pipe(coll):
    """The pipe the crew lays in S21-S24: on short supports along the water line from the north-east gate to the
    sapling, with the bend that rises over the great root instead of cutting it."""
    pm = world.mat("crew_pipe", "painted_metal", "#4f7fa8", wear=0.45, dirt=0.6, tile=1.0)
    sup = world.mat("pipe_support", "painted_metal", "#3c4248", wear=0.5, dirt=0.7, tile=1.0)
    d = 1 / math.sqrt(2)
    # (distance along the line from the gate, height): the line meets the root about 18 m from the gate
    prof = [(-3.0, 0.35), (16.0, 0.35), (17.6, 1.25), (20.4, 1.25), (22.0, 0.35), (40.8, 0.35)]
    ax, ay = PIPE_LINE[0]
    for (s0, z0), (s1, z1) in zip(prof, prof[1:]):
        x0, y0 = ax - s0 * d, ay - s0 * d
        x1, y1 = ax - s1 * d, ay - s1 * d
        L = math.dist((x0, y0, z0), (x1, y1, z1))
        seg = world.box(coll, "crew_pipe", (L + 0.12, 0.34, 0.34), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                        pm, 0.05, shape="cylinder_x")
        seg.rotation_euler = (0, -math.atan2(z1 - z0, math.hypot(x1 - x0, y1 - y0)), math.atan2(y1 - y0, x1 - x0))
        world.box(coll, "pipe_collar", (0.18, 0.44, 0.44), (x1, y1, z1), sup, 0.03, shape="cylinder_x",
                  rot=math.atan2(y1 - y0, x1 - x0))
    for s_ in range(0, 41, 3):
        if 15.5 < s_ < 22.5:
            continue
        x, y = ax - s_ * d, ay - s_ * d
        world.box(coll, "pipe_support", (0.5, 0.12, 0.2), (x, y, 0.1), sup, 0.02, rot=math.pi / 4)


def _great_tree(coll, rnd, ctrl):
    """The great old tree on the north-east side; one big root arches across the water line."""
    gx, gy = GREAT_TREE
    plants.tree(coll, rnd, gx, gy, ctrl, height=15.5, girth=1.5, bark="#6a4c38")
    bm = plants.bark_mat("#6a4c38")
    # the root: three boxes making an arch from the trunk across the line toward the south-east
    # the line passes near (17, 17); the root crosses it heading from the trunk to (22, 13)
    pts = [(gx + 0.6, gy - 0.6, 0.25), (gx + 2.6, gy - 2.6, 0.7), (gx + 4.6, gy - 4.6, 0.55), (gx + 6.4, gy - 6.4, 0.1)]
    for a, b in zip(pts, pts[1:]):
        mx, my, mz = ((a[i] + b[i]) / 2 for i in range(3))
        L = math.dist(a, b)
        r = world.box(coll, "great_root", (L + 0.3, 0.55, 0.5), (mx, my, mz), bm, 0.1)
        r.rotation_euler = (0, -math.atan2(b[2] - a[2], math.hypot(b[0] - a[0], b[1] - a[1])),
                            math.atan2(b[1] - a[1], b[0] - a[0]))


def _trees(coll, rnd, ctrl, clear=()):
    spots = []

    def free(x, y, r):
        if math.hypot(x - SAPLING[0], y - SAPLING[1]) < 6.0 + r:
            return False
        if abs(math.hypot(x, y) - LOOP_R) < 1.6 + r:
            return False
        if _on_line(x, y, 1.4 + r):
            return False
        if math.hypot(x - GREAT_TREE[0], y - GREAT_TREE[1]) < 5.5 + r:
            return False
        if max(abs(x), abs(y)) > HALF - 1.8 - r:
            return False
        if any(math.hypot(x - cx, y - cy) < cr + r * 0.6 for (cx, cy, cr) in clear):
            return False
        return all(math.hypot(x - sx, y - sy) > (r + sr) * 0.8 + 1.0 for (sx, sy, sr) in spots)

    tries = 0
    while len(spots) < 72 and tries < 6000:
        tries += 1
        x, y = rnd.uniform(-HALF, HALF), rnd.uniform(-HALF, HALF)
        h = rnd.uniform(6.5, 11.5)
        r = h * 0.28
        if free(x, y, r):
            spots.append((x, y, r))
            kind = rnd.random()
            bark = rnd.choice(["#7a5a42", "#6e5444", "#82654a"])
            if kind < 0.18:
                plants.column(coll, rnd, x, y, ctrl, height=h * 1.1, girth=rnd.uniform(0.35, 0.5), bark=bark)
            elif kind < 0.36:
                plants.wide(coll, rnd, x, y, ctrl, height=h * 0.8, girth=rnd.uniform(0.5, 0.75), bark=bark)
            else:
                plants.tree(coll, rnd, x, y, ctrl, height=h, girth=rnd.uniform(0.45, 0.75), bark=bark)
    return spots


def _undergrowth(coll, rnd, ctrl, spots):
    """Bushes at tree feet and along the wall, and grass tufts everywhere except the path, denser near trees."""
    for (x, y, r) in spots:
        for _ in range(rnd.randint(1, 3)):
            a, d = rnd.uniform(0, math.tau), rnd.uniform(r * 0.4, r * 0.9)
            bx, by = x + math.cos(a) * d, y + math.sin(a) * d
            if abs(math.hypot(bx, by) - LOOP_R) > 2.0 and math.hypot(bx, by) > 5.0 and max(abs(bx), abs(by)) < HALF - 1:
                plants.bush(coll, rnd, bx, by, ctrl, rnd.uniform(0.6, 1.4))
    for _ in range(60):
        side, u = rnd.randrange(4), rnd.uniform(-HALF + 3, HALF - 3)
        if abs(u) < 4:
            continue
        x, y = [(u, HALF - 1.4), (u, -HALF + 1.4), (HALF - 1.4, u), (-HALF + 1.4, u)][side]
        plants.bush(coll, rnd, x, y, ctrl, rnd.uniform(0.8, 1.6))
    pts = []
    while len(pts) < 2600:
        x, y = rnd.uniform(-HALF + 0.6, HALF - 0.6), rnd.uniform(-HALF + 0.6, HALF - 0.6)
        if abs(math.hypot(x, y) - LOOP_R) < 1.1 or _on_line(x, y, 0.7) or math.hypot(x, y) < 1.15:
            continue
        pts.append((x, y, rnd.uniform(0.7, 1.4)))
    plants.grass(coll, rnd, ctrl, pts, blades=10)


def _city(coll, rnd):
    """Ring road, sidewalks and the towers around the Grove, with the Seed Tower, the Pipeworks block, Grove
    Boulevard to the east and the end of the Fast Lane deck to the west."""
    asphalt = world.tex_mat("asphalt", "asphalt", tile=3.0, rough=0.85, bump=0.5)
    walk = world.tex_mat("sidewalk", "concrete", "#8d8a84", tile=2.0, rough=0.8)
    paint = world.mat("road_paint", "plastic", "#e8e4d8", wear=0.5, dirt=0.4, rough=0.7, tile=1.0)
    world.box(coll, "road", (600, 600, 0.2), (0, 0, -0.25), asphalt, 0)
    for s in (-1, 1):
        world.box(coll, "walk", (2 * WALK_OUT, 4.0, 0.15), (0, s * (ROAD_OUT + 2.0), -0.075), walk, 0.02)
        world.box(coll, "walk", (4.0, 2 * WALK_OUT, 0.15), (s * (ROAD_OUT + 2.0), 0, -0.075), walk, 0.02)
    mid = (ROAD_IN + ROAD_OUT) / 2
    for v in range(int(-ROAD_OUT), int(ROAD_OUT), 4):
        for s in (-1, 1):
            world.box(coll, "dash", (2.0, 0.16, 0.02), (v, s * mid, -0.14), paint, 0)
            world.box(coll, "dash", (0.16, 2.0, 0.02), (s * mid, v, -0.14), paint, 0)
    # buildings: a ring of lots outside the sidewalks, leaving the boulevard (east) and the deck (west) open
    front = WALK_OUT
    lots = []
    for side in ("n", "s", "e", "w"):
        u = -70.0
        while u < 70:
            w = rnd.uniform(11, 16)
            d = rnd.uniform(12, 18)
            c = u + w / 2
            if side == "n":
                x, y = c, front + d / 2
            elif side == "s":
                x, y = c, -front - d / 2
            elif side == "e":
                x, y = front + d / 2, c
                w, d = d, w
            else:
                x, y = -front - d / 2, c
                w, d = d, w
            u += (w if side in "ns" else d) + rnd.uniform(3.0, 5.0)
            if side == "e" and abs(y) < 12:
                continue                                   # Grove Boulevard
            if side == "w" and -22 < y < 6:
                continue                                   # the Fast Lane deck
            if side == "n" and (abs(x) < 14 or 32 < x < 66):
                continue                                   # Seed Tower, Pipeworks
            lots.append((x, y, w, d))
    # the skyline behind: taller, further
    for _ in range(70):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(95, 170)
        x, y = math.cos(a) * r, math.sin(a) * r
        if abs(y) < 14 and x > 0:
            continue
        lots.append((x, y, rnd.uniform(14, 22), rnd.uniform(14, 22)))
    for (x, y, w, d) in lots:
        far = math.hypot(x, y) > 90
        h = rnd.uniform(16, 36) if not far else rnd.uniform(28, 64)
        world.tower(coll, rnd, x, y, w, d, h, rnd.choice(world.PALETTE), rnd.choice(["concrete", "concrete", "corrugated"]))
    # the Seed Tower: old, brick-coloured, 24 m, with the Nursery's greenhouse frame on the roof
    world.tower(coll, random.Random(5), 0, front + 10, 20, 20, 24, "#9c5a48", "concrete")
    bars = world.mat("greenhouse", "painted_metal", "#dfe6e2", wear=0.4, dirt=0.4, tile=1.0)
    for (dx, dy) in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
        world.box(coll, "gh_post", (0.15, 0.15, 3.0), (dx - 2, front + 10 + dy, 25.5 + 0.5), bars, 0.02)
    world.box(coll, "gh_ridge", (6.3, 6.3, 0.15), (-2, front + 10, 27.6), bars, 0.02)
    tank = world.mat("roof_tank", "painted_metal", "#5f7f86", wear=0.5, dirt=0.6, tile=2.0)
    world.box(coll, "nursery_tank", (4.0, 4.0, 4.2), (5, front + 15, 24.0 + 2.1), tank, 0.1, shape="cylinder_z")
    # the Pipeworks: a wide steel-blue block with pipes on its face
    world.tower(coll, random.Random(9), 49, front + 11, 30, 22, 14, "#5f7f86", "corrugated")
    world.pipes(coll, 35, 63, front - 0.4, 2.2)
    # the water main: a pipe climbing the Seed Tower's east face
    pm = world.mat("main_pipe", "painted_metal", "#4f7fa8", wear=0.5, dirt=0.6, tile=1.0)
    world.box(coll, "main_up", (0.7, 0.7, 24), (10.6, front + 2.0, 12), pm, 0.08, shape="cylinder_z")
    # Grove Boulevard: lamps down both sides
    for xb in range(int(WALK_OUT) + 6, 140, 14):
        for s in (-1, 1):
            world.lamp(coll, xb, s * 8.5, math.pi / 2 if s < 0 else -math.pi / 2)
    # the Fast Lane deck: raised slab on piers, stopping short of the wall
    deck = world.tex_mat("deck", "concrete", "#b9b2a4", tile=3.0, rough=0.8)
    yel = world.mat("lane_bar", "plastic", "#e8c22a", wear=0.4, dirt=0.4, tile=1.0)
    x_end = -(HALF + 4.0)
    L = 200
    world.box(coll, "fast_lane_deck", (L, 16, 0.8), (x_end - L / 2, -8, 2.4), deck, 0.06)
    for px in range(int(x_end) - 6, int(x_end) - L, -14):
        for py in (-13, -3):
            world.box(coll, "pier", (1.4, 1.4, 2.0), (px, py, 1.0), deck, 0.05)
    for px in range(int(x_end) - 3, int(x_end) - L, -6):
        world.box(coll, "lane_bar", (3.0, 0.25, 0.03), (px, -8, 2.81), yel, 0.01)
    barrier = world.mat("barrier", "painted_metal", "#e05a2a", wear=0.5, dirt=0.4, tile=1.0)
    for py in range(-14, -1, 3):
        world.box(coll, "barrier", (0.5, 2.6, 1.0), (x_end - 0.8, py + 0.5, 3.3), barrier, 0.05)


def build(sc, tod="morning", water=1.0, seed=11, city=True, pipe=False, clear=()):
    world.CFG = world.TOD[tod]
    world.HAZE = world.CFG["haze"]
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("old_grove")
    sc.collection.children.link(coll)
    world.sky(sc)
    ctrl = plants.control(coll, "grove_water", water)
    _ground(coll, rnd, ctrl)
    _wall(coll)
    _water_line(coll, ctrl)
    _great_tree(coll, rnd, ctrl)
    if pipe:
        _crew_pipe(coll)
    spots = _trees(coll, rnd, ctrl, clear)
    plants.sapling(coll, rnd, SAPLING[0], SAPLING[1], ctrl)
    _undergrowth(coll, rnd, ctrl, spots)
    if city:
        _city(coll, rnd)
    print(f"old_grove: {len(spots) + 1} trees, water={water}, tod={tod}")
    return {"coll": coll, "water": ctrl, "trees": spots}
