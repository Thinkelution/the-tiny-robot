"""The Count House: Ledger's archive of glowing amber data blocks (runs inside Blender).

  import counthouse
  parts = counthouse.build(sc, mood="night", screen="footprints", ladder_x=-3.0, dusty=False, green_handle=False)

Local coordinates: the hall is 26 x 16 m (|x| < 13, |y| < 8) and 14 m high. The main aisle runs east-west down the
middle (|y| < 1.25); the big square reading screen fills the west wall at its end; tall shelves (10 m) of data
blocks line it, with narrow side aisles behind. The rolling ladder hangs from a rail along the north side of the
main aisle (ladder_x places it). A low step block stands by the screen (Tiny hops onto it in S11), and a high square
window in the east wall lets the morning sun lie along the aisle floor (S29).
- every block front is a small amber-glowing face, merged into a few meshes (several thousand blocks stay cheap);
- screen: "off", "bars", "footprints", "footprints_faint", "trees" (pictures from agent/boardart.py);
- dusty: the dusty block with the First Workshop's emblem on the floor by the low shelf (S11);
- green_handle: the one green drawer handle at the bottom of the last shelf (S29).
"""
import math
import random
from pathlib import Path

import bpy

import junk
import world

W, D, H = 13.0, 8.0, 14.0
AISLE = 1.25
RUNS = [(AISLE, -1), (-AISLE, 1), (4.55, -1), (-4.55, 1), (7.1, -1), (-7.1, 1)]   # (front plane y, facing)
SHELF_X = (-9.5, 11.8)
SHELF_H = 10.0
TEX = Path(__file__).resolve().parent.parent / "films" / "the-tiny-robot" / "world" / "textures"
GREEN = (11.2, AISLE + 0.0, 0.32)    # the green handle: last shelf, bottom row, facing the main aisle


def _screen_mat(pic):
    name = f"ch_screen_{pic}"
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
    tex.image = bpy.data.images.load(str(TEX / f"screen_{pic}.png"), check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["UV"], tex.inputs["Vector"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.5
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _shell(coll, mood):
    floor = world.tex_mat("ch_floor", "bark", "#6a4c38", tile=1.2, rough=0.6, bump=0.3)       # worn wooden floor
    wall = world.tex_mat("ch_wall", "concrete", "#5b4c40", tile=2.5, rough=0.85)
    ceil = world.tex_mat("ch_ceil", "concrete", "#3a3029", tile=3.0)
    world.box(coll, "ch_floor", (2 * W, 2 * D, 0.3), (0, 0, -0.15), floor, 0)
    world.box(coll, "ch_ceiling", (2 * W, 2 * D, 0.3), (0, 0, H + 0.15), ceil, 0)
    t = 0.5
    world.box(coll, "ch_wall_w", (t, 2 * D, H), (-W - t / 2, 0, H / 2), wall, 0)
    for s in (-1, 1):
        world.box(coll, "ch_wall_ns", (2 * W + 2 * t, t, H), (0, s * (D + t / 2), H / 2), wall, 0)
    # east wall with the high square window (2 x 2 m) over the aisle, and the door below it
    wx0, wx1, wz0, wz1 = -1.0, 1.0, 9.6, 11.6
    for (y0, y1, z0, z1) in ((-D, wx0, 0, H), (wx1, D, 0, H), (wx0, wx1, 0, wz0), (wx0, wx1, wz1, H)):
        if (y0, y1, z0, z1) == (wx0, wx1, 0, wz0):
            # the door: a gap 1.4 m wide, 2.6 high under the window
            for (a, b) in ((wx0, -0.7), (0.7, wx1)):
                world.box(coll, "ch_wall_e", (t, b - a, wz0), (W + t / 2, (a + b) / 2, wz0 / 2), wall, 0)
            world.box(coll, "ch_wall_e", (t, 1.4, wz0 - 2.6), (W + t / 2, 0, 2.6 + (wz0 - 2.6) / 2), wall, 0)
            continue
        world.box(coll, "ch_wall_e", (t, y1 - y0, z1 - z0), (W + t / 2, (y0 + y1) / 2, (z0 + z1) / 2), wall, 0)
    frame = world.mat("ch_frame", "painted_metal", "#2f2620", wear=0.5, dirt=0.6, tile=1.0)
    world.box(coll, "ch_mullion", (0.3, 0.1, 2.0), (W + 0.1, 0, 10.6), frame, 0.01)
    world.box(coll, "ch_transom", (0.3, 2.0, 0.1), (W + 0.1, 0, 10.6), frame, 0.01)


def _shelves(coll, rnd, green_handle):
    """Shelf frames and their blocks: each front a small glowing amber face; some drawers empty and dark."""
    wood = world.mat("ch_shelf", "painted_metal", "#3b2a1e", wear=0.5, dirt=0.6, tile=1.0)
    amber_hi = world.emissive("ch_amber_hi", "#ffb347", 0.55)
    amber_lo = world.emissive("ch_amber_lo", "#d9802a", 0.22)
    dull = world.mat("ch_dull", "plastic", "#4a3b2c", wear=0.1, dirt=0.4, rough=0.6)
    mats = [wood, amber_hi, amber_lo, dull]
    boxes = []
    x0, x1 = SHELF_X
    cw, rh = 0.46, 0.42
    for (yf, face) in RUNS:
        # the frame: uprights and shelves
        depth = 0.7
        cy = yf - face * depth / 2
        for x in range(int(x0), int(x1) + 1, 3):
            boxes.append(((x, cy, SHELF_H / 2), (0.08, depth, SHELF_H), 0.0, 0))
        for k in range(int(SHELF_H / rh) + 1):
            boxes.append((((x0 + x1) / 2, cy, k * rh), (x1 - x0, depth, 0.04), 0.0, 0))
        # block fronts
        nx = int((x1 - x0) / cw)
        for i in range(nx):
            for j in range(int(SHELF_H / rh)):
                r = rnd.random()
                m = 3 if r < 0.22 else (1 if r < 0.45 else 2)
                bx = x0 + (i + 0.5) * cw
                bz = j * rh + rh / 2 + 0.02
                boxes.append(((bx, yf - face * 0.04, bz), (cw * 0.8, 0.05, rh * 0.72), 0.0, m))   # set back in the shelf
    junk.boxes_mesh("ch_shelves", coll, mats, boxes)
    if green_handle:
        gx, gy, gz = GREEN
        world.box(coll, "green_handle", (0.16, 0.06, 0.08), (gx, gy - 0.07, gz), world.emissive("handle_green", "#6dff8c", 8.0), 0.01)


def _ladder(coll, x):
    """The rolling ladder: a rail along the top of the main aisle's north shelf, and the ladder hooked to it."""
    metal = world.mat("ch_ladder", "bare_metal", "#a8823e", rough=0.4, dirt=0.5, tile=1.0)
    y = AISLE - 0.05
    world.box(coll, "ch_rail", (SHELF_X[1] - SHELF_X[0], 0.08, 0.08), ((SHELF_X[0] + SHELF_X[1]) / 2, y, SHELF_H - 0.3),
              metal, 0.01, shape="cylinder_x")
    world.box(coll, "ch_floor_rail", (SHELF_X[1] - SHELF_X[0], 0.06, 0.04), ((SHELF_X[0] + SHELF_X[1]) / 2, y - 0.9, 0.02),
              metal, 0.0)
    lean = math.atan2(0.9, SHELF_H - 0.3)
    for dx in (-0.35, 0.35):
        st = world.box(coll, "ch_ladder_side", (0.06, 0.06, SHELF_H), (x + dx, y - 0.45, (SHELF_H - 0.3) / 2), metal, 0.01)
        st.rotation_euler.x = -lean
    for k in range(1, 30):
        z = k * 0.33
        world.box(coll, "ch_rung", (0.7, 0.05, 0.05), (x, y - 0.9 + z * math.tan(lean), z), metal, 0.01, shape="cylinder_x")


def build(sc, mood="night", screen="footprints", ladder_x=-3.0, dusty=False, green_handle=False, seed=61):
    world.CFG = world.TOD["night" if mood == "night" else "golden_morning"]
    world.HAZE = world.CFG["haze"]
    rnd = random.Random(seed)
    coll = bpy.data.collections.new("count_house")
    sc.collection.children.link(coll)
    world.sky(sc)
    for ob in sc.collection.objects:
        if ob.type == "LIGHT" and ob.data.type == "SUN":
            if mood == "morning":
                ob.rotation_euler = (math.radians(90 - 28), 0, math.radians(92))   # low from the east, down the aisle
                ob.data.energy *= 2.5
    _shell(coll, mood)
    _shelves(coll, rnd, green_handle)
    _ladder(coll, ladder_x)
    # the reading screen on the west wall, framed, at the aisle's end
    frame = world.mat("ch_frame", "painted_metal", "#2f2620", wear=0.5, dirt=0.6, tile=1.0)
    world.box(coll, "ch_screen_frame", (0.3, 5.6, 5.6), (-W + 0.15, 0, 4.4), frame, 0.05)
    me = bpy.data.meshes.new("ch_screen")
    x = -W + 0.32
    me.from_pydata([(x, 2.5, 1.9), (x, -2.5, 1.9), (x, -2.5, 6.9), (x, 2.5, 6.9)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
    me.materials.append(_screen_mat(screen) if screen != "off" else
                        world.mat("ch_screen_off", "plastic", "#121010", wear=0.0, dirt=0.2, rough=0.15))
    ob = bpy.data.objects.new("ch_screen", me)
    coll.objects.link(ob)
    # the step block by the screen
    step = world.mat("ch_step", "painted_metal", "#6a4c38", wear=0.6, dirt=0.6, tile=1.0)
    world.box(coll, "ch_step", (0.6, 0.6, 0.3), (-8.6, -0.5, 0.15), step, 0.03)
    if dusty:
        dust = world.mat("dusty_block", "plastic", "#8a7a68", wear=0.3, dirt=0.9, rough=0.9)
        world.box(coll, "dusty_block", (0.42, 0.36, 0.3), (-7.6, -0.9, 0.15), dust, 0.03, rot=0.4)
        mark = world.mat("emblem_mark", "plastic", "#3a2e1c", wear=0.0, dirt=0.3, rough=0.6)
        world.box(coll, "dusty_emblem", (0.2, 0.01, 0.16), (-7.6 + 0.07, -0.9 - 0.19, 0.17), mark, 0.0, rot=0.4)
    # warm pendant lamps over the aisle (dim at night, off by day)
    if mood == "night":
        for xl in (-6.0, 0.0, 6.0):
            world.box(coll, "ch_pendant", (0.5, 0.5, 0.25), (xl, 0, 11.5), frame, 0.04)
            world.box(coll, "ch_bulb", (0.25, 0.25, 0.08), (xl, 0, 11.35), world.emissive("ch_bulb", "#ffc070", 16), 0.02)
            ld = bpy.data.lights.new("ch_pendant_light", "SPOT")
            ld.energy = 900
            ld.color = (1.0, 0.7, 0.4)
            ld.spot_size = math.radians(80)
            ld.spot_blend = 0.6
            lo = bpy.data.objects.new("ch_pendant_light", ld)
            coll.objects.link(lo)
            lo.location = (xl, 0, 11.3)
    else:
        ld = bpy.data.lights.new("ch_fill", "AREA")
        ld.energy = 600
        ld.size = 8.0
        ld.color = (1.0, 0.85, 0.7)
        lo = bpy.data.objects.new("ch_fill", ld)
        coll.objects.link(lo)
        lo.location = (0, 0, 13.0)
    print(f"count_house: mood={mood}, screen={screen}")
    return {"coll": coll}
