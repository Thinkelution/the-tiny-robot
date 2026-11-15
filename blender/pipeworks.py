"""The Pipeworks interior, and the hidden valve room behind its blank wall (runs inside Blender).

  import pipeworks
  parts = pipeworks.build(sc, mood="afternoon", lever="down", bent=True, tree_gauge=0.15, nursery=1.0)

Local coordinates: the room is 30 x 22 m (|x| < 15, |y| < 11) and 12 m high, +Y is north. Laid out from the beats:
- the gauge panel stands in the middle of the room facing south, with rows of round lights, the big lever, a ledge
  Tiny can hop onto (0.35 m) and a waist-high railing in front (one bar bent by Dash in S05, when bent=True);
- right behind the panel is a flat, blank grey wall (y = 8.5) with nothing on it, except a narrow square gap low
  down where a pipe passes through (Tiny squeezes through it in S12);
- behind that wall, the cramped valve room (1.6 m deep): the lever's linkage bar enters a big valve that splits the
  water, one pipe up through the ceiling to the Nursery, one pipe down into the floor toward the Grove, and beside
  the down pipe a square gauge with a tree shape (green / amber / red from tree_gauge);
- steel-blue and green square pipes climb every other wall on brackets; amber warning lamps on the walls;
- high on the west wall the rooftop pipe enters beside a small square hatch (Tiny's way in), with a crate below;
- doors: a side door east (Dash's entrance), a far door west, the big doorway south (Quota fills it in S19), and
  a high window on the south wall (grey with rain in S25);
- stacks of spare pipe segments near the east door.
Moods: afternoon (a sun shaft through the high window), night and late_night (amber lamps are the light),
pre_dawn (grey window light).
"""
import math
import random

import bpy

import plants
import world

W, D, H = 15.0, 11.0, 12.0
PANEL = (0.0, 6.2)
BLANK_Y = 8.5
VALVE_Y = BLANK_Y + 1.0
GAP = (4.6, 0.26)               # (x, centre z) of the square gap in the blank wall
MOODS = {
    # tod preset for the sky through the window, lamp energy, lamp colour, fill energy, fill colour
    "afternoon": ("afternoon", 150, (1.0, 0.55, 0.15), 500, (0.85, 0.9, 1.0)),
    "night": ("night", 420, (1.0, 0.5, 0.12), 260, (0.45, 0.55, 0.85)),
    "late_night": ("night", 380, (1.0, 0.48, 0.1), 120, (0.4, 0.5, 0.85)),
    "pre_dawn": ("pre_dawn", 320, (1.0, 0.5, 0.12), 700, (0.62, 0.68, 0.8)),
}


def _light(coll, name, kind, loc, energy, color, size=0.3, rot=None, spot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    else:
        ld.shadow_soft_size = size
    if spot:
        ld.spot_size = math.radians(spot)
        ld.spot_blend = 0.6
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob


def _shell(coll):
    floor = world.tex_mat("pw_floor", "concrete", "#6e6c68", tile=2.5, rough=0.75)
    wall = world.tex_mat("pw_wall", "corrugated", "#5c6b74", tile=1.4, rough=0.7)
    blank = world.tex_mat("pw_blank", "concrete", "#8c8c88", tile=3.0, rough=0.85, bump=0.2)
    ceil = world.tex_mat("pw_ceiling", "corrugated", "#3d4247", tile=1.6)
    world.box(coll, "pw_floor", (2 * W, 2 * D, 0.3), (0, 0, -0.15), floor, 0)
    world.box(coll, "pw_ceiling", (2 * W, 2 * D, 0.3), (0, 0, H + 0.15), ceil, 0)
    # outer walls, with openings: south doorway (4 x 4.6) and high window, east and west side doors (1.8 x 2.6)
    t = 0.4
    # north wall (behind the valve room)
    world.box(coll, "pw_wall_n", (2 * W, t, H), (0, D + t / 2, H / 2), wall, 0)
    # south wall in pieces round the doorway and the window
    # south wall: the doorway (|x| < 2, z < 4.6) and above it the high window (|x| < 4, 7.4 < z < 10.2)
    for (x0, x1, z0, z1) in ((-W, -4.0, 0, H), (4.0, W, 0, H), (-4.0, -2.0, 0, 7.4), (2.0, 4.0, 0, 7.4),
                             (-2.0, 2.0, 4.6, 7.4), (-4.0, 4.0, 10.2, H)):
        world.box(coll, "pw_wall_s", (x1 - x0, t, z1 - z0), ((x0 + x1) / 2, -D - t / 2, (z0 + z1) / 2), wall, 0)
    for s in (-1, 1):       # east / west walls with a side door at y = -4 (east) / -6 (west)
        yd = -4.0 if s > 0 else -6.0
        x = s * (W + t / 2)
        lo, hi = -D, yd - 0.9
        world.box(coll, "pw_wall_ew", (t, hi - lo, H), (x, (lo + hi) / 2, H / 2), wall, 0)
        lo, hi = yd + 0.9, D
        world.box(coll, "pw_wall_ew", (t, hi - lo, H), (x, (lo + hi) / 2, H / 2), wall, 0)
        world.box(coll, "pw_wall_ew", (t, 1.8, H - 2.6), (x, yd, 2.6 + (H - 2.6) / 2), wall, 0)
    # the high window: a frame and mullions in the south wall, left of the doorway
    frame = world.mat("pw_frame", "painted_metal", "#2f353c", wear=0.4, dirt=0.6, tile=1.0)
    # (an open frame: the opening itself is left in the wall pieces below, so the sun can come in)
    for k in range(5):
        world.box(coll, "pw_mullion", (0.12, 0.5, 2.9), (-4.0 + k * 2.0, -D - 0.1, 8.8), frame, 0.01)
    world.box(coll, "pw_transom", (8.0, 0.5, 0.12), (0, -D - 0.1, 8.8), frame, 0.01)
    # the blank grey wall: full height, across the middle of the north end, with the square gap low on it
    gx, gz = GAP
    half = 7.0
    world.box(coll, "pw_blank", (gx - 0.25 + half, 0.35, H), ((-half + gx - 0.25) / 2, BLANK_Y, H / 2), blank, 0)
    world.box(coll, "pw_blank", (half - gx - 0.25, 0.35, H), ((gx + 0.25 + half) / 2, BLANK_Y, H / 2), blank, 0)
    world.box(coll, "pw_blank", (0.5, 0.35, H - 0.52), (gx, BLANK_Y, 0.52 + (H - 0.52) / 2), blank, 0)
    # the valve room's side walls close it off (so it is a hidden space)
    for s in (-1, 1):
        world.box(coll, "pw_valve_side", (0.35, D - BLANK_Y, H), (s * half, (D + BLANK_Y) / 2, H / 2), blank, 0)
    # roof trusses
    for x in range(-12, 13, 4):
        world.box(coll, "pw_truss", (0.3, 2 * D, 0.5), (x, 0, H - 0.6), frame, 0.02)


def _pipes(coll, rnd):
    """Square pipes in steel blue and green on brackets along the south, east and west walls."""
    blue = world.mat("pw_pipe_blue", "painted_metal", "#4f7fa8", wear=0.45, dirt=0.6, tile=1.0)
    green = world.mat("pw_pipe_green", "painted_metal", "#4f8a6a", wear=0.45, dirt=0.6, tile=1.0)
    brk = world.mat("pw_bracket", "painted_metal", "#2f353c", wear=0.5, dirt=0.7, tile=1.0)
    valve = world.mat("pw_valve", "painted_metal", "#b0412e", wear=0.5, dirt=0.5, tile=1.0)
    for (axis, fixed, lo, hi) in (("x", -D + 0.5, -W + 0.6, W - 0.6), ("y", W - 0.5, -D + 0.6, BLANK_Y - 0.5),
                                  ("y", -W + 0.5, -D + 0.6, BLANK_Y - 0.5)):
        for k, z in enumerate((1.2, 2.4, 4.0, 6.2, 8.8)):
            if axis == "x" and z > 7.5:
                continue                                   # the high window
            s = rnd.uniform(0.35, 0.6)
            m = blue if (k + int(fixed)) % 2 else green
            L = hi - lo
            off = 0.25 + s / 2 + (k % 2) * 0.25
            inward = 1 if fixed < 0 else -1
            if axis == "x":
                # skip the doorway span
                for (a, b) in ((lo, -2.3), (2.3, hi)) if z < 5 else ((lo, hi),):
                    world.box(coll, "pw_pipe", (b - a, s, s), ((a + b) / 2, fixed + inward * off, z), m, 0.04)
            else:
                yd = -4.0 if fixed > 0 else -6.0
                spans = ((lo, yd - 1.2), (yd + 1.2, hi)) if z < 3.2 else ((lo, hi),)
                for (a, b) in spans:
                    world.box(coll, "pw_pipe", (s, b - a, s), (fixed + inward * off, (a + b) / 2, z), m, 0.04)
        # risers and brackets
        for u in range(int(lo) + 2, int(hi) - 1, 5):
            if axis == "x" and abs(u) < 3:
                continue
            s = rnd.uniform(0.4, 0.7)
            m = green if u % 2 else blue
            x, y = (u, fixed + (0.6 if fixed < 0 else -0.6)) if axis == "x" else (fixed + (0.6 if fixed < 0 else -0.6), u)
            if axis == "y" and abs(u - (-4.0 if fixed > 0 else -6.0)) < 1.6:
                continue
            world.box(coll, "pw_riser", (s, s, H - 0.6), (x, y, (H - 0.6) / 2), m, 0.04)
            world.box(coll, "pw_valve_wheel", (0.12, 0.6, 0.6), (x, y, 1.6), valve, 0.05, shape="cylinder_x")
            for z in (2.0, 5.0, 8.0):
                world.box(coll, "pw_bracket", (s + 0.2, s + 0.2, 0.15), (x, y, z), brk, 0.02)


def _panel(coll, lever, bent, nursery_ctrl, sprout_ctrl):
    """The gauge panel, the big lever, Tiny's ledge and the railing; returns the lever handle's location."""
    px, py = PANEL
    body = world.mat("pw_panel", "painted_metal", "#3f4a52", wear=0.45, dirt=0.6, tile=1.0)
    face = world.mat("pw_panel_face", "painted_metal", "#2a3036", wear=0.3, dirt=0.5, tile=1.0)
    world.box(coll, "pw_panel", (4.2, 0.9, 2.6), (px, py, 1.3), body, 0.06)
    world.box(coll, "pw_panel_face", (3.9, 0.06, 1.3), (px, py - 0.47, 1.85), face, 0.02)
    world.box(coll, "pw_ledge", (4.2, 0.7, 0.35), (px, py - 0.8, 0.175), body, 0.04)
    # rows of round lights: dull ones, plus the sprout light (the Nursery) and the main-line light
    dull = world.mat("pw_light_off", "plastic", "#3a3f44", wear=0.0, dirt=0.2, rough=0.25)
    amber = world.emissive("pw_light_amber", "#ffb347", 3.0)
    lights = []
    for r, z in enumerate((2.3, 1.95, 1.6)):
        for c in range(9):
            x = px - 1.6 + c * 0.4
            if r == 1 and c == 2:
                m = plants.gauge_mat("pw_sprout", sprout_ctrl)          # the Nursery / sprout light
            elif r == 1 and c == 6:
                m = plants.gauge_mat("pw_nursery", nursery_ctrl)
            else:
                m = amber if (r * 9 + c) % 5 == 0 else dull
            lights.append(world.box(coll, "pw_light", (0.2, 0.08, 0.2), (x, py - 0.5, z), m, 0.07,
                                    shape="cylinder_y"))
    # the lever: a slot on the panel's right, the arm and a big handle; up = 2.2 m, down = 0.95 m
    metal = world.mat("pw_lever", "bare_metal", "#9aa0a6", rough=0.35, dirt=0.4, tile=1.0)
    grip = world.mat("pw_grip", "rubber", "#c0392b", wear=0.2, dirt=0.4, tile=1.0)
    lx = px + 1.6
    world.box(coll, "pw_slot", (0.2, 0.1, 1.5), (lx, py - 0.48, 1.55), face, 0.02)
    hz = 2.2 if lever == "up" else 0.95
    pivot = (lx, py - 0.55, 1.55)
    ang = math.atan2(hz - pivot[2], 0.9)
    arm = world.box(coll, "pw_lever_arm", (0.95, 0.12, 0.12), (lx, py - 0.55 - 0.45 * math.cos(ang),
                                                               pivot[2] + 0.45 * math.sin(ang)), metal, 0.02)
    arm.rotation_euler = (ang, 0, math.pi / 2)
    handle = (lx, py - 0.55 - 0.9 * math.cos(ang), pivot[2] + 0.9 * math.sin(ang))
    world.box(coll, "pw_lever_grip", (0.6, 0.18, 0.18), handle, grip, 0.06, shape="cylinder_x")
    # railing: waist high (1.1 m), round the front of the panel; one bar bent when bent=True
    rail = world.mat("pw_rail", "painted_metal", "#e8b62a", wear=0.5, dirt=0.5, tile=1.0)
    ry = py - 2.2
    for x in (-2.6, -1.3, 0.0, 1.3, 2.6):
        world.box(coll, "pw_rail_post", (0.08, 0.08, 1.1), (px + x, ry, 0.55), rail, 0.01)
    for (x0, x1) in ((-2.6, -1.3), (-1.3, 0.0), (0.0, 1.3), (1.3, 2.6)):
        if bent and x0 == 1.3:
            # the dented bar: a crooked angle where Dash's corner clipped it
            world.box(coll, "pw_rail_bent", (0.75, 0.07, 0.07), (px + 1.62, ry - 0.18, 1.02), rail, 0.01, rot=-0.55)
            world.box(coll, "pw_rail_bent", (0.75, 0.07, 0.07), (px + 2.28, ry - 0.18, 1.02), rail, 0.01, rot=0.55)
        else:
            world.box(coll, "pw_rail", (x1 - x0, 0.07, 0.07), (px + (x0 + x1) / 2, ry, 1.08), rail, 0.01)
    for x in (-2.6, 2.6):
        world.box(coll, "pw_rail_side", (0.07, 1.4, 0.07), (px + x, ry + 0.7, 1.08), rail, 0.01)
    # the linkage bar: from the lever's pivot back through the blank wall into the valve room
    world.box(coll, "pw_linkage", (0.1, BLANK_Y + 1.0 - py, 0.1), (lx, (py + BLANK_Y + 1.0) / 2, 1.55), metal, 0.02)
    return handle


def _valve_room(coll, tree_ctrl):
    """Behind the blank wall: the valve that splits the water, the pipe up to the Nursery, the pipe down into the
    floor toward the Grove, and the tree gauge."""
    blue = world.mat("pw_pipe_blue", "painted_metal", "#4f7fa8", wear=0.45, dirt=0.6, tile=1.0)
    valve = world.mat("pw_bigvalve", "painted_metal", "#6b4a3a", wear=0.5, dirt=0.7, tile=1.0)
    lx = PANEL[0] + 1.6
    vy = VALVE_Y + 0.3
    world.box(coll, "pw_valve_body", (1.2, 1.0, 1.2), (lx, vy, 1.55), valve, 0.15)
    world.box(coll, "pw_pipe_in", (6.0, 0.55, 0.55), (lx - 3.6, vy, 1.55), blue, 0.05)       # the main, from the west
    world.box(coll, "pw_pipe_up", (0.55, 0.55, H - 2.1), (lx + 0.9, vy, 2.1 + (H - 2.1) / 2), blue, 0.05)
    world.box(coll, "pw_pipe_up_knee", (1.0, 0.55, 0.55), (lx + 0.55, vy, 1.55), blue, 0.05)
    world.box(coll, "pw_pipe_down", (0.55, 0.55, 1.6), (lx - 0.9, vy, 0.75), blue, 0.05)       # into the floor
    world.box(coll, "pw_floor_collar", (0.9, 0.9, 0.08), (lx - 0.9, vy, 0.02), valve, 0.03)
    # the pipe that runs through the gap in the blank wall
    gx, gz = GAP
    world.box(coll, "pw_gap_pipe", (0.22, 4.0, 0.22), (gx, BLANK_Y, gz - 0.02), blue, 0.03)
    # the tree gauge: a square housing, the light, and a tree shape over it
    house = world.mat("pw_gauge_house", "painted_metal", "#2a3036", wear=0.3, dirt=0.5, tile=1.0)
    gx2 = lx - 1.7
    world.box(coll, "pw_tree_gauge", (0.5, 0.18, 0.5), (gx2, vy - 0.35, 0.95), house, 0.03)
    g = plants.gauge_mat("pw_tree", tree_ctrl)
    world.box(coll, "pw_tree_lamp", (0.36, 0.05, 0.36), (gx2, vy - 0.45, 0.95), g, 0.02)
    shape = world.mat("pw_tree_shape", "plastic", "#111418", wear=0.0, dirt=0.1, rough=0.4)
    world.box(coll, "pw_tree_trunk", (0.05, 0.02, 0.14), (gx2, vy - 0.48, 0.86), shape, 0.0)
    world.box(coll, "pw_tree_crown", (0.18, 0.02, 0.13), (gx2, vy - 0.48, 0.99), shape, 0.02)
    # the gauge's own glow: the only light in here
    col = (1.0, 0.1, 0.05)
    w = tree_ctrl["water"]
    if w > 0.7:
        col = (0.25, 1.0, 0.35)
    elif w > 0.3:
        col = (1.0, 0.45, 0.05)
    _light(coll, "pw_tree_glow", "POINT", (gx2, vy - 0.65, 0.95), 45, col, 0.15)
    return (gx2, vy - 0.45, 0.95)


def _props(coll, rnd):
    blue = world.mat("pw_pipe_blue", "painted_metal", "#4f7fa8", wear=0.45, dirt=0.6, tile=1.0)
    green = world.mat("pw_pipe_green", "painted_metal", "#4f8a6a", wear=0.45, dirt=0.6, tile=1.0)
    # stacks of spare pipe segments near the east door
    for (cx, cy) in ((9.5, -2.6), (9.5, 2.4)):
        for layer in range(3):
            for k in range(4 - layer):
                s = 0.5
                world.box(coll, "pw_spare", (4.0, s, s), (cx, cy + (k - (3 - layer) / 2) * (s + 0.04),
                                                         s / 2 + layer * s), blue if (k + layer) % 2 else green, 0.04)
    # the rooftop pipe entering high on the west wall, with Tiny's hatch, and a crate below
    hatch = world.mat("pw_hatch", "painted_metal", "#7d8288", wear=0.5, dirt=0.6, tile=1.0)
    world.box(coll, "pw_roof_pipe", (0.5, 0.5, 4.5), (-W + 0.8, -1.0, H - 2.25), blue, 0.05)
    world.box(coll, "pw_roof_pipe_run", (0.5, 9.0, 0.5), (-W + 0.8, 3.5, 7.0), blue, 0.05)
    world.box(coll, "pw_hatch", (0.1, 0.6, 0.6), (-W + 0.25, -0.2, 7.6), hatch, 0.02)
    wood = world.mat("pw_crate", "painted_metal", "#8a5a3c", wear=0.6, dirt=0.6, tile=1.2)
    for (x, y, s, z) in ((-W + 1.4, 1.2, 1.0, 0), (-W + 1.4, 1.2, 0.8, 1.0), (-W + 2.5, 1.0, 0.7, 0)):
        world.box(coll, "pw_crate", (s, s, s), (x, y, z + s / 2), wood, 0.04)
    # the main water line along the floor of the north end, feeding the valve room through its west side
    world.box(coll, "pw_main", (8.0, 0.6, 0.6), (-11.0, BLANK_Y - 0.8, 0.5), blue, 0.05)


def _lamps(coll, energy, color):
    """Amber warning lamps on the walls: a caged box that glows, plus a light so the pipes catch it."""
    cage = world.mat("pw_cage", "painted_metal", "#2f353c", wear=0.4, dirt=0.6, tile=1.0)
    glow = world.emissive("pw_warning", "#ffa21f", 12.0)
    spots = [(-W + 0.35, -8, 5.5, 0), (-W + 0.35, 4, 5.5, 0), (W - 0.35, -8, 5.5, 0), (W - 0.35, 4, 5.5, 0),
             (-9, -D + 0.35, 5.5, 1), (9, -D + 0.35, 5.5, 1), (-5.5, BLANK_Y - 0.25, 7.5, 1),
             (5.5, BLANK_Y - 0.25, 7.5, 1)]
    for (x, y, z, along_x) in spots:
        world.box(coll, "pw_lamp_cage", (0.45, 0.45, 0.6), (x, y, z), cage, 0.04)
        world.box(coll, "pw_lamp", (0.32, 0.32, 0.4), (x, y, z), glow, 0.06)
        dx = 0.0 if along_x else (0.6 if x < 0 else -0.6)
        dy = (0.6 if y < 0 else -0.6) if along_x else 0.0
        _light(coll, "pw_warning_light", "POINT", (x + dx, y + dy, z), energy, color, 0.25)


def build(sc, mood="afternoon", lever="down", bent=True, tree_gauge=0.5, nursery=1.0, sprout=None, seed=23):
    tod, lamp_e, lamp_c, fill_e, fill_c = MOODS[mood]
    world.CFG = world.TOD[tod]
    world.HAZE = world.CFG["haze"]
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("pipeworks")
    sc.collection.children.link(coll)
    world.sky(sc)
    if mood == "afternoon":
        # indoors the window shaft is the key light: a stronger sun than outside, a dim cool fill
        for ob in sc.collection.objects:
            if ob.type == "LIGHT" and ob.data.type == "SUN":
                ob.data.energy *= 3.0
    tree_ctrl = plants.control(coll, "tree_gauge", tree_gauge)
    nursery_ctrl = plants.control(coll, "nursery_gauge", nursery)
    sprout_ctrl = plants.control(coll, "sprout_gauge", nursery if sprout is None else sprout)
    _shell(coll)
    _pipes(coll, rnd)
    handle = _panel(coll, lever, bent, nursery_ctrl, sprout_ctrl)
    gauge = _valve_room(coll, tree_ctrl)
    _props(coll, rnd)
    _lamps(coll, lamp_e, lamp_c)
    # soft fill from the roof (a working room is never pitch black): big area lights under the trusses
    for x in (-8, 0, 8):
        ob = _light(coll, "pw_fill", "AREA", (x, -2, H - 1.2), fill_e, fill_c, size=6.0)
        ob.data.size_y = 6.0
        ob.data.shape = "RECTANGLE"
        ob.visible_volume_scatter = False
    if mood != "afternoon":
        # a caged work lamp hanging over the panel: a warm pool on the lever and the ledge
        cage = world.mat("pw_cage", "painted_metal", "#2f353c", wear=0.4, dirt=0.6, tile=1.0)
        px, py = PANEL
        world.box(coll, "pw_work_cable", (0.03, 0.03, H - 6.2), (px, py - 1.4, 6.2 + (H - 6.2) / 2), cage, 0.0)
        world.box(coll, "pw_work_shade", (0.7, 0.7, 0.3), (px, py - 1.4, 6.05), cage, 0.05)
        world.box(coll, "pw_work_bulb", (0.3, 0.3, 0.12), (px, py - 1.4, 5.86), world.emissive("pw_bulb", "#ffc070", 20), 0.05)
        _light(coll, "pw_work_lamp", "SPOT", (px, py - 1.4, 5.8), 2200, (1.0, 0.66, 0.32), 0.25, spot=70)
    print(f"pipeworks: mood={mood}, lever={lever}, tree gauge={tree_gauge}")
    return {"coll": coll, "handle": handle, "tree_gauge": gauge, "ledge_z": 0.35}
