"""The Foundry: the cavernous hall of the Logic Press (runs inside Blender).

  import foundry
  parts = foundry.build(sc, mood="night", pen_open=False, crowd=False, plate=False)

Local coordinates: the hall is 56 x 38 m (|x| < 28, |y| < 19) and 20 m high. The Logic Press stands at the far west
end; the great doors (14 m wide, 12 m high) fill the middle of the east wall and open onto Foundry Yard, so the
morning sun comes straight in through them (S28: "a gold bar of sunrise cuts across the orange-lit floor").
- the Logic Press: a base slab, four square columns, a crown, and the ram with its pistons raised, a glowing plate
  slot on the ram's underside, and a painted square floor mark directly beneath (where Warden sets the crate);
- the rack of blank core plates beside it;
- the fenced square holding pen (Mossback's sad little square), its gate on the east side, open or shut;
- the orange glow from below: molten channels in the floor along both walls and a glowing pit round the Press base;
- square pipes along the walls running out through the doors; the yard and the street outside.
Moods: night (orange from below, cool blue night in the doorway) and morning (the sunrise through the doors).
"""
import math
import random

import bpy

import crowd
import world

W, D, H = 28.0, 19.0, 20.0
PRESS_X = -19.0
DOOR_W, DOOR_H = 14.0, 12.0
PEN = (-4.0, 10.5, 8.0)          # centre x, y, side
CRATE_MARK = (PRESS_X, 0.0)


def _light(coll, name, kind, loc, energy, color, size=0.5, rot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    else:
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob


def _shell(coll):
    floor = world.tex_mat("fd_floor", "metal_plate", "#5a5650", tile=2.0, rough=0.7)
    wall = world.tex_mat("fd_wall", "concrete", "#6e625a", tile=3.0, rough=0.8)
    roof = world.tex_mat("fd_roof", "corrugated", "#3d3a38", tile=2.0)
    frame = world.mat("fd_steel", "painted_metal", "#2f2b29", wear=0.5, dirt=0.7, tile=2.0)
    world.box(coll, "fd_floor", (2 * W, 2 * D, 0.3), (0, 0, -0.15), floor, 0)
    world.box(coll, "fd_roof", (2 * W, 2 * D, 0.4), (0, 0, H + 0.2), roof, 0)
    t = 0.6
    world.box(coll, "fd_wall_w", (t, 2 * D, H), (-W - t / 2, 0, H / 2), wall, 0)
    for s in (-1, 1):
        world.box(coll, "fd_wall_ns", (2 * W + 2 * t, t, H), (0, s * (D + t / 2), H / 2), wall, 0)
        # east wall either side of the great doors, and above them
        world.box(coll, "fd_wall_e", (t, D - DOOR_W / 2, H), (W + t / 2, s * (DOOR_W / 2 + (D - DOOR_W / 2) / 2), H / 2),
                  wall, 0)
    world.box(coll, "fd_wall_e_top", (t, DOOR_W, H - DOOR_H), (W + t / 2, 0, DOOR_H + (H - DOOR_H) / 2), wall, 0)
    # the great doors: two huge leaves swung open against the outside wall
    door = world.mat("fd_door", "painted_metal", "#5a3a2c", wear=0.7, dirt=0.7, tile=2.0)
    for s in (-1, 1):
        leaf = world.box(coll, "fd_door_leaf", (0.4, DOOR_W / 2, DOOR_H), (W + 0.6 + DOOR_W / 4 * 0.0 + 3.5,
                                                                         s * (DOOR_W / 2 + 0.3), DOOR_H / 2), door, 0.05)
        leaf.rotation_euler.z = s * math.radians(80)
    # roof trusses and high clerestory slits
    for x in range(-24, 27, 6):
        world.box(coll, "fd_truss", (0.5, 2 * D, 0.9), (x, 0, H - 1.0), frame, 0.03)
    # floor seams (the ones Tiny hops over)
    seam = world.mat("fd_seam", "plastic", "#1a1816", wear=0.0, dirt=0.3, rough=0.9)
    for x in range(-24, 27, 4):
        world.box(coll, "fd_seam", (0.08, 2 * D, 0.02), (x, 0, 0.005), seam, 0.0)


def _glow(coll, strength):
    """Orange light from below: molten channels along the long walls and a glowing pit round the Press base."""
    melt = world.emissive("fd_melt", "#ff6a1a", strength)
    grate = world.mat("fd_grate", "painted_metal", "#2a2624", wear=0.4, dirt=0.7, tile=1.0)
    for s in (-1, 1):
        world.box(coll, "fd_channel", (2 * W - 6, 0.9, 0.06), (-1.0, s * (D - 1.4), 0.0), melt, 0.0)
        for x in range(-25, 25, 2):
            world.box(coll, "fd_channel_bar", (0.12, 1.1, 0.08), (x, s * (D - 1.4), 0.04), grate, 0.01)
        for x in (-20, -8, 4, 16):
            # area lights face down by default: flip them so the channels light the hall from below
            _light(coll, "fd_underglow", "AREA", (x, s * (D - 1.4), 0.3), 2400, (1.0, 0.42, 0.12), 3.0,
                   rot=(math.pi, 0, 0))
    # the pit round the Press base
    for (dx, dy, sx, sy) in ((0, -7.2, 16, 1.0), (0, 7.2, 16, 1.0), (-7.5, 0, 1.0, 14.4), (7.5, 0, 1.0, 14.4)):
        world.box(coll, "fd_pit", (sx, sy, 0.06), (PRESS_X + dx, dy, 0.0), melt, 0.0)
    for (dx, dy) in ((0, -7.2), (0, 7.2), (-7.5, 0), (7.5, 0)):
        ob = _light(coll, "fd_pitglow", "AREA", (PRESS_X + dx, dy, 0.3), 2600, (1.0, 0.45, 0.14), 2.5)
        ob.rotation_euler = (math.pi, 0, 0)


def _press(coll, plate):
    """The Logic Press: a cliff of slabs and pistons with a glowing plate slot."""
    steel = world.tex_mat("press_steel", "metal_plate", "#3b3836", tile=2.0, rough=0.55)
    dark = world.mat("press_dark", "painted_metal", "#1f1d1c", wear=0.4, dirt=0.7, tile=2.0)
    brass = world.mat("press_brass", "bare_metal", "#a8823e", rough=0.4, dirt=0.6, tile=1.0)
    x = PRESS_X
    world.box(coll, "press_base", (12, 12, 1.2), (x, 0, 0.6), steel, 0.08)
    world.box(coll, "press_anvil", (5, 5, 0.6), (x, 0, 1.5), dark, 0.05)
    for (dx, dy) in ((-4.5, -4.5), (4.5, -4.5), (-4.5, 4.5), (4.5, 4.5)):
        world.box(coll, "press_column", (1.6, 1.6, 15.0), (x + dx, dy, 1.2 + 7.5), steel, 0.08)
    world.box(coll, "press_crown", (13.5, 13.5, 3.2), (x, 0, 16.2 + 1.6), steel, 0.1)
    # the ram, raised, on four pistons
    world.box(coll, "press_ram", (8.0, 8.0, 2.2), (x, 0, 10.2), dark, 0.08)
    for (dx, dy) in ((-2.4, -2.4), (2.4, -2.4), (-2.4, 2.4), (2.4, 2.4)):
        world.box(coll, "press_piston", (1.1, 1.1, 5.0), (x + dx, dy, 11.3 + 2.5), brass, 0.05, shape="cylinder_z")
    # the glowing plate slot on the ram's underside, and (S28) one blank plate in it
    slot = world.emissive("press_slot", "#ffb347", 12.0)
    world.box(coll, "press_slot", (2.4, 1.6, 0.08), (x, 0, 9.06), slot, 0.0)
    if plate:
        world.box(coll, "press_plate", (2.2, 1.4, 0.12), (x, 0, 8.96), world.emissive("plate_glow", "#ffe6a0", 6.0), 0.02)
    _light(coll, "press_slot_light", "POINT", (x, 0, 8.6), 900, (1.0, 0.7, 0.35), 0.6)
    # the square floor mark beneath it
    paint = world.mat("fd_mark", "plastic", "#e8b62a", wear=0.5, dirt=0.5, rough=0.7, tile=1.0)
    for (dx, dy, sx, sy) in ((0, -1.0, 2.2, 0.12), (0, 1.0, 2.2, 0.12), (-1.0, 0, 0.12, 2.2), (1.0, 0, 0.12, 2.2)):
        world.box(coll, "fd_mark", (sx, sy, 0.02), (x + 6.8 + dx, dy, 0.01), paint, 0.0)
    # warning stripes on the base
    yel = world.mat("press_stripe", "painted_metal", "#e8b62a", wear=0.6, dirt=0.6, tile=1.0)
    for k in range(-5, 6, 2):
        world.box(coll, "press_stripe", (0.06, 0.8, 1.0), (x + 6.03, k, 0.6), yel, 0.0, rot=0.0)


def _rack(coll):
    frame = world.mat("rack_frame", "painted_metal", "#2f2b29", wear=0.5, dirt=0.6, tile=1.0)
    blank = world.mat("blank_plate", "bare_metal", "#c9c4b8", rough=0.25, dirt=0.3, tile=1.0)
    rx, ry = PRESS_X + 9.5, -9.0
    for (dx, dz) in ((-2.2, 0), (2.2, 0)):
        world.box(coll, "rack_post", (0.2, 0.2, 3.2), (rx + dx, ry, 1.6), frame, 0.02)
    for k in range(4):
        world.box(coll, "rack_shelf", (4.6, 0.8, 0.08), (rx, ry, 0.5 + k * 0.8), frame, 0.01)
        for j in range(8):
            world.box(coll, "blank_plate", (0.05, 0.6, 0.42), (rx - 1.9 + j * 0.54, ry, 0.5 + k * 0.8 + 0.25), blank,
                      0.005, rot=0.0)


def _pen(coll, open_gate):
    bars = world.mat("pen_bars", "painted_metal", "#4a4f57", wear=0.6, dirt=0.6, tile=1.0)
    cx, cy, s = PEN
    h = 2.2
    for side in range(4):
        for k in range(17):
            t = -s / 2 + k * s / 16
            if side == 0:
                x, y = cx + t, cy - s / 2
            elif side == 1:
                x, y = cx + t, cy + s / 2
            elif side == 2:
                x, y = cx - s / 2, cy + t
            else:
                x, y = cx + s / 2, cy + t
                if open_gate and abs(t) < 1.6:
                    continue                         # the gate is swung open
            world.box(coll, "pen_bar", (0.08, 0.08, h), (x, y, h / 2), bars, 0.01)
    for (cx2, cy2, sx, sy) in ((cx, cy - s / 2, s, 0.12), (cx, cy + s / 2, s, 0.12), (cx - s / 2, cy, 0.12, s)):
        for z in (0.3, h):
            world.box(coll, "pen_rail", (sx, sy, 0.1), (cx2, cy2, z), bars, 0.01)
    for (y0, y1) in ((cy - s / 2, cy - 1.6), (cy + 1.6, cy + s / 2)):
        for z in (0.3, h):
            world.box(coll, "pen_rail", (0.12, y1 - y0, 0.1), (cx + s / 2, (y0 + y1) / 2, z), bars, 0.01)
    if open_gate:
        gate = world.box(coll, "pen_gate", (3.2, 0.1, h * 0.9), (cx + s / 2 + 1.6 * 0.7, cy - 1.6 + 1.6 * 0.7, h / 2),
                         bars, 0.02)
        gate.rotation_euler.z = math.radians(45)
    # the worn square track Mossback has rolled into the floor
    worn = world.mat("pen_track", "plastic", "#3a3632", wear=0.0, dirt=0.5, rough=0.9)
    for (dx, dy, sx, sy) in ((0, -2.6, 5.6, 0.9), (0, 2.6, 5.6, 0.9), (-2.6, 0, 0.9, 5.6), (2.6, 0, 0.9, 5.6)):
        world.box(coll, "pen_track", (sx, sy, 0.012), (cx + dx, cy + dy, 0.006), worn, 0.0)


def _pipes(coll):
    pm = world.mat("fd_pipe", "painted_metal", "#6b4a3a", wear=0.6, dirt=0.7, tile=1.0)
    for s in (-1, 1):
        for z in (6.5, 8.0):
            world.box(coll, "fd_pipe", (2 * W - 2, 0.6, 0.6), (0, s * (D - 0.6), z), pm, 0.05)
        for x in range(-24, 27, 6):
            world.box(coll, "fd_pipe_bracket", (0.3, 0.9, 2.0), (x, s * (D - 0.5), 7.2), pm, 0.02)


def _outside(coll, rnd, mood):
    yard = world.tex_mat("fd_yard", "concrete", "#8a867e", tile=2.5, rough=0.85)
    world.box(coll, "fd_yard", (300, 300, 0.2), (150 + W, 0, -0.1), yard, 0)
    for _ in range(26):
        x, y = W + rnd.uniform(25, 130), rnd.uniform(-90, 90)
        if abs(y) < 14 + (x - W) * 0.05:
            continue                                   # keep the view (and the sunrise) through the doors open
        world.tower(coll, rnd, x, y, rnd.uniform(12, 20), rnd.uniform(12, 20), rnd.uniform(14, 40),
                    rnd.choice(world.PALETTE), rnd.choice(["concrete", "corrugated"]))
    if world.CFG["lamps"] > 0:
        for y in (-12.0, 12.0):
            world.lamp(coll, W + 8.0, y, math.pi if y > 0 else 0.0)


def crate_with_tiny(coll, x, y, eyes="green", z=0.0, rot=0.0):
    """Warden's carrying crate with Tiny inside: a plain box, a narrow slot, two small eye-lights in it."""
    wood = world.mat("carry_crate", "painted_metal", "#9a7a58", wear=0.6, dirt=0.6, tile=1.0)
    world.box(coll, "carry_crate", (0.62, 0.62, 0.55), (x, y, z + 0.275), wood, 0.02, rot=rot)
    slot = world.mat("crate_slot", "plastic", "#0b0b0c", wear=0.0, dirt=0.1, rough=0.9)
    c, s = math.cos(rot), math.sin(rot)
    fx, fy = x + 0.315 * c, y + 0.315 * s
    world.box(coll, "crate_slot", (0.02, 0.36, 0.08), (fx, fy, z + 0.36), slot, 0.0, rot=rot)
    col = {"green": "#7dffa0", "amber": "#ffb347"}[eyes]
    for k in (-1, 1):
        world.box(coll, "crate_eye", (0.022, 0.05, 0.04), (fx + 0.004 * c - k * 0.06 * s, fy + 0.004 * s + k * 0.06 * c,
                                                          z + 0.36), world.emissive(f"crate_eye_{eyes}", col, 6.0), 0.0,
                  rot=rot)


def build(sc, mood="night", pen_open=False, crowd_n=0, plate=False, crate=None, seed=53):
    world.CFG = world.TOD["night" if mood == "night" else "sunrise"]
    world.HAZE = world.CFG["haze"]
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("foundry")
    sc.collection.children.link(coll)
    world.sky(sc)
    if mood == "morning":
        for ob in sc.collection.objects:
            if ob.type == "LIGHT" and ob.data.type == "SUN":
                ob.data.energy *= 2.5            # the gold bar through the doors is the key light
    _shell(coll)
    _glow(coll, 6.0 if mood == "night" else 3.0)
    _press(coll, plate)
    _rack(coll)
    _pen(coll, pen_open)
    _pipes(coll)
    _outside(coll, rnd, mood)
    if crate:
        crate_with_tiny(coll, *crate)
    if crowd_n:
        spots = crowd.spots_in(rnd, W + 0.8, W + 14.0, -6.5, 6.5, crowd_n, face_x=-1, spacing=1.1)
        crowd.build(coll, rnd, spots, "off")
    print(f"foundry: mood={mood}, pen open={pen_open}, crowd={crowd_n}")
    return {"coll": coll, "mark": (PRESS_X + 6.8, 0.0)}
