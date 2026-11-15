"""S02 "Mossback's Loop", the whole scene on one timeline (runs inside Blender; called by animshot.py).

Every character acts in story time; cameras cut between beats (timeline markers bind each camera). Where the
script skips time between beats (Tiny crossing the Grove, Mossback going round its loop) a robot is moved on a
cut frame, where no camera sees the jump.

Staging (Grove coordinates): the sapling at the origin; Mossback's loop is a ring 10 m out; the scrap chute stands
at the edge of the sapling's clearing at CHUTE, its mouth facing west; Primly sweeps a row of fallen leaves and the
cube seed east along y = ROW_Y into it. Tiny enters by the north gate (y = 32).
"""
import math

import bpy
from mathutils import Vector

import anim
import grove
import world

FPS = 24
ROW_Y = -1.6
CHUTE = (3.75, ROW_Y)
SEED_HOME = (0.52, -0.72)

# (first frame, speaker, line): shown as subtitles in post until voices exist
LINES = [
    (190, "TINY", "Check... no harm. Go."),
    (470, "MOSSBACK", "Good morning, little..."),
    (690, "MOSSBACK", "...one. The sapling grew."),
    (745, "TINY", "I saw! It reaches my eyes now."),
    (965, "PRIMLY", "Excuse me, that is not where that goes."),
    (1058, "PRIMLY", "And that moss is not tidy."),
    (1110, "MOSSBACK", "Moss is not..."),
    (1540, "MOSSBACK", "...mess. It is growing."),
]
SOUNDS = [(410, "a deep gurgle from Mossback's tank"), (800, "whisk-whisk, whisk-whisk"),
          (1690, "a bright fanfare from the Big Board, far away")]


def loop_pt(deg):
    a = math.radians(deg)
    return (math.cos(a) * grove.LOOP_R, math.sin(a) * grove.LOOP_R)


def loop_path(d0, d1, step=4):
    n = max(2, int(abs(d1 - d0) / step))
    return [loop_pt(d0 + (d1 - d0) * k / n) for k in range(n + 1)]


def _cam(sc, name, loc, target, lens, focus=None, fstop=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.03
    cd.clip_end = 2000
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if focus is not None and fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_object = focus
    return cam


def _cut(sc, f, cam):
    m = sc.timeline_markers.new(f"cut_{f}", frame=f)
    m.camera = cam


def _props(sc):
    coll = sc.collection
    # the scrap chute: a square hopper on a short post, mouth facing west toward the sapling
    metal = world.mat("chute", "painted_metal", "#6b6f74", wear=0.6, dirt=0.7, tile=1.0)
    cx, cy = CHUTE
    world.box(coll, "chute_post", (0.18, 0.18, 0.35), (cx + 0.35, cy, 0.17), metal, 0.02)
    world.box(coll, "chute_floor", (0.7, 0.62, 0.04), (cx + 0.2, cy, 0.12), metal, 0.01)
    for s in (-1, 1):
        world.box(coll, "chute_side", (0.7, 0.04, 0.3), (cx + 0.2, cy + s * 0.31, 0.27), metal, 0.01)
    world.box(coll, "chute_back", (0.04, 0.62, 0.42), (cx + 0.55, cy, 0.33), metal, 0.01)
    lip = world.box(coll, "chute_lip", (0.05, 0.62, 0.05), (cx - 0.14, cy, 0.14), metal, 0.01)
    world.box(coll, "chute_hole", (0.3, 0.5, 0.01), (cx + 0.3, cy, 0.145),
              world.mat("chute_dark", "plastic", "#0c0c0d", wear=0.0, dirt=0.1, rough=0.9), 0.0)
    # the leaves Primly sweeps, and the cube seed among them
    leaf_m = world.mat("s02_leaf", "plastic", "#8a7038", wear=0.0, dirt=0.2, tile=1.0)
    leaves = []
    for k, x in enumerate((1.55, 1.95, 2.3, 2.7)):
        leaves.append(world.box(coll, "swept_leaf", (0.24, 0.17, 0.016), (x, ROW_Y + (k % 2 - 0.5) * 0.12, 0.012),
                                leaf_m, 0.004, rot=0.4 + k))
    seed_m = world.mat("cube_seed", "painted_metal", "#7a5a32", wear=0.3, dirt=0.5, tile=1.0)
    seed = world.box(coll, "cube_seed", (0.17, 0.17, 0.17), (2.1, ROW_Y + 0.05, 0.085), seed_m, 0.035)
    sprout = world.box(coll, "seed_sprout", (0.02, 0.02, 0.05), (0, 0, 0.11), world.mat("seed_sprout", "plastic",
                       "#7cc456", wear=0.0, dirt=0.1, tile=1.0), 0.005)
    sprout.parent = seed
    # the leaf Tiny walks round at the gate, the paved apron outside it
    world.box(coll, "gate_leaf", (0.26, 0.18, 0.018), (0.0, 30.55, 0.012), leaf_m, 0.004, rot=0.5)
    pave = world.tex_mat("gate_apron", "concrete", "#9a958a", tile=1.5, rough=0.85)
    world.box(coll, "gate_apron", (3.4, 3.2, 0.2), (0.0, 33.6, -0.1), pave, 0.02)
    # Mossback's water: a stream under the spout, hidden until the pour
    water = bpy.data.materials.new("pour_water")
    water.use_nodes = True
    b = next(n for n in water.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.75, 0.88, 1.0, 1)
    b.inputs["Transmission Weight"].default_value = 0.9
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["IOR"].default_value = 1.33
    stream = world.box(coll, "pour_stream", (0.05, 0.05, 0.7), (0, 0, 0), water, 0.02, shape="cylinder_z")
    return leaves, seed, stream


def build(sc, roots):
    tiny = anim.Actor(next(r for r, sp in roots if sp["id"] == "tiny"))
    moss = anim.Actor(next(r for r, sp in roots if sp["id"] == "mossback"))
    prim = anim.Actor(next(r for r, sp in roots if sp["id"] == "primly"))
    leaves, seed, stream = _props(sc)
    sc["keep_clear"] = [(CHUTE[0], CHUTE[1], 0.8), (2.2, ROW_Y, 0.9), (0.0, 30.55, 0.22), (0.0, 0.0, 1.15),
                        (SEED_HOME[0], SEED_HOME[1], 0.2)]
    cams = {}

    # ---------------- B1 (1-96): the Grove waking up; Mossback far across on its loop
    cams["b1"] = _cam(sc, "cam_b1", (-7.0, -27.0, 15.0), (1.0, 2.0, 0.5), 28)
    c = cams["b1"]
    c.keyframe_insert("location", frame=1)
    c.location = (-6.2, -24.5, 13.2)
    c.keyframe_insert("location", frame=96)
    _cut(sc, 1, c)
    moss.place(1, *loop_pt(20), yaw_deg=None)
    moss.walk(loop_path(20, 40), start=1, speed=0.55)
    prim.place(1, 30.0, -30.0, 0)               # off stage
    tiny.place(1, 0.0, 33.6, 0)

    # ---------------- B2 (97-336): the gate, the check, round the leaf
    cams["b2"] = _cam(sc, "cam_b2", (0.85, 28.2, 0.3), (-0.1, 33.0, 0.42), 34, tiny.root, 2.8)
    c = cams["b2"]
    c.keyframe_insert("location", frame=97)
    c.location = (0.95, 27.1, 0.32)
    c.keyframe_insert("location", frame=336)
    _cut(sc, 97, c)
    f = tiny.walk([(0.0, 33.6), (0.0, 32.55)], start=104, speed=0.5)
    f = tiny.check(f + 6)
    tiny.walk([(0.0, 32.55), (0.0, 31.6), (0.45, 30.9), (0.45, 30.3), (0.1, 29.95)], start=f + 4, speed=0.5)

    # ---------------- B3 (337-456): Mossback rolls into frame on its loop and waters a tree; Tiny watches
    tiny.place(337, 1.4, 13.6, 165)
    moss.place(337, *loop_pt(62), yaw_deg=None)
    moss.walk(loop_path(62, 88), start=337, speed=0.5)
    cams["b3"] = _cam(sc, "cam_b3", (3.3, 15.6, 0.45), (0.2, 9.6, 0.9), 26, moss.root, 4.0)
    _cut(sc, 337, cams["b3"])
    # the pour: the tank tilts toward its spout, a stream runs, the tank rights itself
    moss.rotate(372, "tank", 24, frames=10, axis=1)
    moss.rotate(420, "tank", 0, frames=10, axis=1)
    nozzle = moss.joint("spout_nozzle")
    stream.parent = nozzle
    stream.location = (0.05, 0.0, -0.36)
    for (fr, sz) in ((1, 0.0), (378, 0.0), (384, 1.0), (418, 1.0), (424, 0.0)):
        anim.key_prop(stream, fr, scale=(sz, sz, max(sz, 0.001)))
    tiny.turn_to(400, look_at=loop_pt(80), frames=10)

    # ---------------- B4 (457-528): "Good morning, little..." close on Mossback rolling past
    moss.walk(loop_path(88, 104), start=457, speed=0.5)
    cams["b4"] = _cam(sc, "cam_b4", (0.6, 13.0, 0.9), (-2.0, 9.6, 0.75), 32, moss.root, 4.0)
    _cut(sc, 457, cams["b4"])
    moss.expr(470, happy=0.6)
    moss.expr(520)

    # ---------------- B5 (529-648): Mossback rolls on and away; Tiny turns to follow; then waits by the sapling
    moss.walk(loop_path(104, 124), start=529, speed=0.5)
    cams["b5a"] = _cam(sc, "cam_b5a", (2.9, 15.0, 0.42), (-2.0, 10.0, 0.6), 28, tiny.root, 3.2)
    _cut(sc, 529, cams["b5a"])
    tiny.turn_to(540, look_at=loop_pt(112), frames=14)
    tiny.turn_to(566, look_at=loop_pt(122), frames=14)
    tiny.place(589, 0.85, -0.55, 125)
    cams["b5b"] = _cam(sc, "cam_b5b", (2.0, -2.3, 0.38), (0.25, 0.0, 0.62), 30, tiny.root, 3.2)
    _cut(sc, 589, cams["b5b"])
    tiny.look(600, 0.0, 1.0)            # up the sapling
    tiny.look(616, 0.0, -0.6)           # down
    tiny.look(630, 0.0, 0.4)
    tiny.blink(640)

    # ---------------- B6 (649-720): Mossback trundles back round from the far side: "...one. The sapling grew."
    moss.place(649, *loop_pt(196), yaw_deg=None)
    moss.walk(loop_path(196, 214), start=649, speed=0.5)
    cams["b6"] = _cam(sc, "cam_b6", (2.2, 0.9, 0.5), (-8.5, -2.8, 0.8), 30, moss.root, 5.6)
    _cut(sc, 649, cams["b6"])
    tiny.turn_to(652, look_at=loop_pt(205), frames=10)

    # ---------------- B7 (721-792): "I saw! It reaches my eyes now."
    cams["b7"] = _cam(sc, "cam_b7", (-0.95, 0.85, 0.34), (0.75, -0.5, 0.36), 32, tiny.root, 2.8)
    _cut(sc, 721, cams["b7"])
    tiny.turn_to(724, look_at=(0.0, 0.0), frames=8)
    tiny.expr(745, happy=1.0)
    tiny.look(745, 0.0, 0.8)
    tiny.expr(785)
    tiny.look(785, 0.0, 0.0)

    # ---------------- B8 (793-960): whisk-whisk; Primly glides in straight, turns a right angle, sweeps the row
    prim.place(793, 1.15, 6.0, 0)
    f = prim.walk([(1.15, 6.0), (1.15, ROW_Y)], start=800, speed=0.9, turn=0.05)
    f = prim.turn_to(f + 2, yaw_deg=90, frames=5)                 # face east (+X)
    sweep0 = f + 2
    prim.walk([(1.15, ROW_Y), (2.95, ROW_Y)], start=sweep0, speed=0.32, turn=0.05)
    cams["b8"] = _cam(sc, "cam_b8", (-0.6, -6.6, 1.5), (2.3, 0.0, 0.9), 26)
    _cut(sc, 793, cams["b8"])
    tiny.turn_to(808, look_at=(1.15, 2.0), frames=10)

    # ---------------- B9 (961-1008): "Excuse me, that is not where that goes."
    cams["b9"] = _cam(sc, "cam_b9", (0.6, -4.8, 1.4), (1.9, ROW_Y, 1.35), 32, prim.root, 4.0)
    _cut(sc, 961, cams["b9"])
    prim.expr(965, squint=0.6)

    # ---------------- B10 (1009-1104): Mossback rolls past Primly; Primly's head swivels to the moss
    moss.place(1009, *loop_pt(300), yaw_deg=None)
    moss.walk(loop_path(300, 330), start=1009, speed=0.5)
    cams["b10"] = _cam(sc, "cam_b10", (0.2, -6.8, 1.1), (5.5, -4.2, 1.0), 26)
    _cut(sc, 1009, cams["b10"])
    prim.rotate(1030, "head", -70, frames=5)
    prim.expr(1036, squint=1.0)

    # ---------------- B11 (1105-1152): "Moss is not..." Mossback rolling on
    moss.place(1105, *loop_pt(330), yaw_deg=None)
    moss.walk(loop_path(330, 346), start=1105, speed=0.5)
    cams["b11"] = _cam(sc, "cam_b11", (5.2, -1.8, 1.0), (9.0, -4.2, 0.8), 30, moss.root, 4.0)
    _cut(sc, 1105, cams["b11"])

    # ---------------- B12 (1153-1248): Primly pushes the row into the chute; the seed catches on the lip; Primly
    # turns a right angle and glides away, still sweeping
    prim.rotate(1153, "head", 0, frames=5)
    prim.expr(1153)
    sweep_end = 1200
    prim.walk([(2.95, ROW_Y), (3.25, ROW_Y)], start=1160, speed=0.3, turn=0.05)
    prim.sweep(sweep0, sweep_end)
    # leaves and seed move ahead of the brooms: into the chute (leaves) and onto its lip (seed)
    for k, lf in enumerate(leaves):
        x0 = lf.location.x
        anim.key_prop(lf, sweep0, loc=(x0, lf.location.y, 0.012))
        anim.key_prop(lf, sweep0 + 30 + k * 8, loc=(x0 + 0.5, lf.location.y, 0.012))
        anim.key_prop(lf, sweep_end - 6, loc=(CHUTE[0] + 0.1, ROW_Y, 0.14))
        anim.key_prop(lf, sweep_end, loc=(CHUTE[0] + 0.3, ROW_Y, -0.2))          # down the hole
    anim.key_prop(seed, sweep0, loc=tuple(seed.location))
    anim.key_prop(seed, sweep_end - 4, loc=(CHUTE[0] - 0.24, ROW_Y + 0.05, 0.085))
    anim.key_prop(seed, sweep_end + 2, loc=(CHUTE[0] - 0.22, ROW_Y + 0.05, 0.13))   # caught on the lip
    f = prim.turn_to(1206, yaw_deg=180, frames=5)                   # face north (+Y)... the front is -Y: yaw 180
    prim.walk([(3.25, ROW_Y), (3.25, 7.5)], start=f + 2, speed=0.8, turn=0.05)
    prim.sweep(f + 2, 1290)
    cams["b12"] = cams["b8"]
    _cut(sc, 1153, cams["b8"])

    # ---------------- B13 (1249-1344): Tiny tiptoes to the chute, checks, hugs the seed
    f = tiny.walk([(0.85, -0.55), (2.1, -1.2), (3.2, -1.45)], start=1252, speed=0.45)
    tiny.look(f + 2, -1.0)
    tiny.look(f + 10, 1.0)
    tiny.look(f + 18, 0.0, 0.3)                                     # toward Primly's back
    tiny.hands(f + 22, "hug", frames=6)
    pick = f + 28
    cams["b13"] = _cam(sc, "cam_b13", (1.5, -3.1, 0.36), (3.15, -1.4, 0.3), 30, tiny.root, 3.2)
    _cut(sc, 1249, cams["b13"])

    # ---------------- B14 (to ~1520): Tiny waddles back with the seed, round each leaf, sets it by the sapling
    back0 = pick + 4
    f = tiny.walk([(3.2, -1.45), (2.3, -2.0), (1.4, -1.6), (0.95, -1.0)], start=back0, speed=0.32, swing=False)
    tiny.carry(seed, pick, f)
    anim.key_prop(seed, f + 6, loc=(SEED_HOME[0], SEED_HOME[1], 0.085))
    tiny.hands(f + 6, "rest", frames=6)
    tiny.hands(f + 14, "up", frames=3)                                # one little pat
    tiny.hands(f + 18, "rest", frames=3)
    set_down = f + 22
    cams["b14"] = _cam(sc, "cam_b14", (-0.6, -3.4, 0.4), (1.6, -1.2, 0.3), 28, tiny.root, 3.2)
    _cut(sc, back0 + 30, cams["b14"])

    # ---------------- B15 (from 1530): "...mess. It is growing." (Mossback, far off)
    # ---------------- B16 (1581-1680): Primly's head snaps round; Tiny freezes, hands behind its back
    snap = max(1581, set_down + 8)
    prim.rotate(snap, "head", 180, frames=3)
    tiny.hands(snap + 2, "behind", frames=3)
    tiny.expr(snap + 2, wide=1.0)
    tiny.look(snap + 2, 0.0, 0.0)
    prim.expr(snap + 20, squint=0.7)
    prim.blink(snap + 34)
    prim.blink(snap + 42)
    prim.rotate(snap + 60, "head", 0, frames=6)
    tiny.expr(snap + 70)
    tiny.hands(snap + 72, "rest", frames=6)
    cams["b16"] = _cam(sc, "cam_b16", (-1.8, -4.6, 1.2), (2.0, 2.4, 1.2), 26)
    _cut(sc, snap - 6, cams["b16"])

    # ---------------- B17 (fanfare, then everyone leaves): antenna amber, a look toward the towers; Primly
    # glides off toward the sound; Tiny a last look at the sapling and hurries after
    fan = snap + 96
    tiny.antenna(fan + 6, "amber")
    tiny.turn_to(fan + 8, yaw_deg=-90 + 180, frames=10)              # toward the east, Main Square
    f = prim.turn_to(fan + 14, yaw_deg=90 + 180 - 180, frames=5)
    prim.walk([(3.25, 7.5), (12.0, 7.5)], start=f + 2, speed=0.8, turn=0.05)
    tiny.turn_to(fan + 40, look_at=(0.0, 0.0), frames=8)
    tiny.look(fan + 48, 0.0, 0.7)
    f = tiny.walk([(0.95, -1.0), (2.4, 0.4), (5.0, 2.6)], start=fan + 62, speed=0.6)
    cams["b17"] = _cam(sc, "cam_b17", (-2.6, -3.4, 0.6), (3.6, 1.2, 0.8), 26, tiny.root, 4.0)
    _cut(sc, fan, cams["b17"])
    end = f + 8

    for a in (tiny, moss, prim):
        a.idle(1, end)
    sc.frame_end = end
    return end
