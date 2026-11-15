"""Quota's Fast Lane Works, the road that stops dead at the Old Grove's west gate (runs inside Blender).

  import fastlane
  fastlane.road(coll, state="straight", night=False, pipe_line=False)    # called by grove._city (Grove coordinates)

The road runs dead straight along y = 0 from the industrial west edge and stops 2 m short of the Grove wall, pointing
through the west gate at the trees. Far out it is a raised deck on square piers; from x = -110 it ramps down to a
slab road raised one kerb (0.35 m) above the street, so at its end Quota's lowered blade hangs a hand's width above
the ground and Tiny can walk out of the gate into the gap between the blade and the trees (S08).
- state "straight" (S08, S21): striped barriers across the unfinished end, Quota's painted parking box.
- state "curve" (S27): the barriers dragged into a smooth curve that bends south off the road and follows the ring
  road round the Grove's south-west corner.
- night: the floodlights on square poles are lit (S21).
- pipe_line: the line of square pipe the crew lays in S21, from the road's end through the gate toward the sapling,
  with spare segments stacked by the slab piles.
"""
import math

import bpy

import world

X_END = -34.3            # the road's end: 2 m short of the Grove wall (x = -32)
WIDTH = 16.0
TOP = 0.35               # the at-grade slab road's top
DECK = 2.8               # the raised deck's top, far out
RAMP = (-110.0, -70.0)   # the ramp from deck to grade
CURVE = [(-62.0, -6.0), (-52.0, -16.0), (-45.0, -27.0), (-38.0, -36.5), (-26.0, -38.5), (-10.0, -38.5), (8.0, -38.5)]


def _barrier(coll, x, y, rot, mats):
    stripe_a, stripe_b, foot = mats
    world.box(coll, "barrier_foot", (0.5, 2.4, 0.18), (x, y, TOP + 0.09), foot, 0.03, rot=rot)
    for k in range(4):
        world.box(coll, "barrier_band", (0.36, 2.2, 0.2), (x, y, TOP + 0.28 + k * 0.2), stripe_a if k % 2 else stripe_b,
                  0.03, rot=rot)


def road(coll, state="straight", night=False, pipe_line=False):
    deck = world.tex_mat("fl_deck", "concrete", "#b9b2a4", tile=3.0, rough=0.8)
    edge = world.tex_mat("fl_edge", "concrete", "#8f8a80", tile=1.5)
    yel = world.mat("lane_bar", "plastic", "#e8c22a", wear=0.4, dirt=0.4, tile=1.0)
    # at grade: x from RAMP[1] to X_END, top at TOP
    L = X_END - RAMP[1]
    world.box(coll, "fl_slab", (L, WIDTH, TOP + 0.2), ((RAMP[1] + X_END) / 2, 0, (TOP - 0.2) / 2), deck, 0.03)
    # the ramp: a sloped slab
    r0, r1 = RAMP
    rl = math.hypot(r1 - r0, DECK - TOP)
    ramp = world.box(coll, "fl_ramp", (rl, WIDTH, 0.6), ((r0 + r1) / 2, 0, (DECK + TOP) / 2 - 0.3), deck, 0.03)
    ramp.rotation_euler.y = math.atan2(DECK - TOP, r1 - r0)
    # the raised deck out west, on square piers
    L2 = 160.0
    world.box(coll, "fl_deck", (L2, WIDTH, 0.8), (r0 - L2 / 2, 0, DECK - 0.4), deck, 0.04)
    for px in range(int(r0) - 8, int(r0 - L2), -16):
        for py in (-5.0, 5.0):
            world.box(coll, "fl_pier", (1.6, 1.6, DECK - 0.8), (px, py, (DECK - 0.8) / 2), edge, 0.05)
    # kerbs and lane bars
    for s in (-1, 1):
        world.box(coll, "fl_kerb", (L + 0.2, 0.4, 0.22), ((RAMP[1] + X_END) / 2, s * (WIDTH / 2 - 0.2), TOP + 0.11), edge, 0.03)
    for x in range(int(X_END) - 4, int(RAMP[1]), -6):
        for y in (-WIDTH / 6, WIDTH / 6):
            world.box(coll, "lane_bar", (3.0, 0.22, 0.02), (x, y, TOP + 0.01), yel, 0.005)
    # the unfinished end: a rough broken edge with rebar sticking out
    rebar = world.mat("rebar", "bare_metal", "#6b4a3a", rough=0.6, dirt=0.8, tile=1.0)
    for k in range(14):
        y = -WIDTH / 2 + 0.6 + k * (WIDTH - 1.2) / 13
        world.box(coll, "rebar", (0.9, 0.03, 0.03), (X_END + 0.35, y, TOP - 0.12), rebar, 0.0, rot=(k % 3 - 1) * 0.12)
    # Quota's parking box at the very end, facing the trees
    paint = world.mat("fl_paint", "plastic", "#e8e4d8", wear=0.5, dirt=0.5, rough=0.7, tile=1.0)
    px = X_END - 3.2
    for (dx, dy, sx, sy) in ((0, -2.4, 4.6, 0.15), (0, 2.4, 4.6, 0.15), (-2.3, 0, 0.15, 4.8)):
        world.box(coll, "park_line", (sx, sy, 0.02), (px + dx, dy, TOP + 0.01), paint, 0.0)
    # barriers
    mats = (world.mat("barrier_orange", "painted_metal", "#e05a2a", wear=0.5, dirt=0.4, tile=1.0),
            world.mat("barrier_white", "painted_metal", "#e8e4d8", wear=0.5, dirt=0.5, tile=1.0),
            world.mat("barrier_foot", "painted_metal", "#3c4248", wear=0.5, dirt=0.6, tile=1.0))
    if state == "straight":
        for k in range(6):
            y = -WIDTH / 2 + 1.4 + k * 2.65
            if abs(y) < 2.0:
                continue                                     # a gap in the middle: the way Tiny walks out (S08)
            _barrier(coll, X_END - 0.7, y, 0.0, mats)
        for x in (-46.0, -52.0, -58.0):                      # side barriers along the works
            _barrier(coll, x, -WIDTH / 2 - 1.0, math.pi / 2, mats)
    else:
        # dragged into a curve: barriers spaced along CURVE, each turned along the line
        pts = []
        for (a, b) in zip(CURVE, CURVE[1:]):
            L = math.dist(a, b)
            n = max(1, int(L / 3.2))
            for k in range(n):
                t = k / n
                pts.append(((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), math.atan2(b[1] - a[1], b[0] - a[0])))
        for ((x, y), ang) in pts:
            _barrier(coll, x, y, ang + math.pi / 2, mats)
    # stacked road slabs and spare pipe by the works
    slab = world.tex_mat("road_slab", "concrete", "#a39d92", tile=1.5)
    for k in range(4):
        world.box(coll, "road_slab", (6.0, 3.0, 0.4), (-60.0, 13.0 + (k % 2) * 0.3, 0.2 + k * 0.42), slab, 0.03,
                  rot=(k % 2) * 0.06)
        world.box(coll, "road_slab", (6.0, 3.0, 0.4), (-60.0, 17.0, 0.2 + k * 0.42), slab, 0.03, rot=-(k % 2) * 0.05)
    # floodlights on square poles
    pole = world.mat("flood_pole", "painted_metal", "#3c4248", wear=0.5, dirt=0.6, tile=1.0)
    for (x, y) in ((-40.0, -10.5), (-40.0, 10.5), (-56.0, -10.5), (-56.0, 10.5)):
        h = 9.0
        world.box(coll, "flood_pole", (0.4, 0.4, h), (x, y, h / 2), pole, 0.03)
        head = world.box(coll, "flood_head", (1.2, 0.5, 0.7), (x, y - math.copysign(0.4, y), h), pole, 0.05)
        if night:
            world.box(coll, "flood_glass", (1.0, 0.05, 0.5), (x, y - math.copysign(0.68, y), h - 0.05),
                      world.emissive("flood_glow", "#f4f6ff", 30), 0.0)
            ld = bpy.data.lights.new("floodlight", "SPOT")
            ld.energy = 9000
            ld.color = (0.92, 0.95, 1.0)
            ld.spot_size = math.radians(70)
            ld.spot_blend = 0.4
            ld.shadow_soft_size = 0.4
            ob = bpy.data.objects.new("floodlight", ld)
            coll.objects.link(ob)
            ob.location = (x, y - math.copysign(0.8, y), h - 0.2)
            aim = (X_END - 4.0 - x, -y * 0.5, -h)
            from mathutils import Vector
            ob.rotation_euler = Vector(aim).to_track_quat("-Z", "Y").to_euler()
    if pipe_line:
        pm = world.mat("crew_pipe", "painted_metal", "#4f7fa8", wear=0.45, dirt=0.6, tile=1.0)
        sup = world.mat("pipe_support", "painted_metal", "#3c4248", wear=0.5, dirt=0.7, tile=1.0)
        # laid: from the road's end through the gate, 2 m segments, the last few still to come
        for k in range(9):
            x0 = X_END - 1.0 + k * 2.05
            world.box(coll, "crew_pipe", (2.0, 0.34, 0.34), (x0 + 1.0, 1.4, 0.32), pm, 0.04, shape="cylinder_x")
            world.box(coll, "pipe_collar", (0.16, 0.44, 0.44), (x0 + 2.0, 1.4, 0.32), sup, 0.03, shape="cylinder_x")
        for k in range(6):
            world.box(coll, "spare_pipe", (2.0, 0.34, 0.34), (-50.0, -12.5 + (k % 3) * 0.38, 0.17 + (k // 3) * 0.34),
                      pm, 0.04, shape="cylinder_x")
