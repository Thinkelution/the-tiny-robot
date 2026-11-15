"""Look-development stills of a set, with cast robots placed for scale (runs inside Blender).

  blender -b --factory-startup -P blender/setshot.py -- <out_dir> <shot> [<shot> ...] [--samples N] [--res WxH]
            [--device HIP|OPTIX] [--preview]

Shots are defined in SHOTS below: the set, time of day, water level, camera, and which robots stand where.
Writes <out_dir>/<shot>.png. Each shot builds its scene from scratch, so shots can differ in time of day.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grove  # noqa: E402
import look  # noqa: E402
import counthouse  # noqa: E402
import foundry  # noqa: E402
import junk  # noqa: E402
import mainsquare  # noqa: E402
import nursery  # noqa: E402
import pipeworks  # noqa: E402
import robot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAST = ROOT / "films" / "the-tiny-robot" / "cast"

argv = sys.argv[sys.argv.index("--") + 1:]
opts, args = {}, []
i = 0
while i < len(argv):
    if argv[i].startswith("--"):
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            opts[argv[i][2:]] = "1"
            i += 1
    else:
        args.append(argv[i])
        i += 1
OUT = Path(args[0]).resolve()   # absolute: Blender reads a bare relative path from the drive root
OUT.mkdir(parents=True, exist_ok=True)
RES = tuple(int(v) for v in opts.get("res", "1920x1080").split("x"))
SAMPLES = int(opts.get("samples", 64))

# camera: (location, target, lens mm, f-stop or None)
# robots: (id, x, y, yaw) with yaw = degrees, or ("cam", offset) to face the camera then turn by the offset;
#         x = "loop" puts the robot on Mossback's loop at the first angle (from y degrees, stepping 6) where the
#         camera can see it
# clear: (x, y, r) spots kept free of trees, so a camera or a staging spot is not inside a trunk
SHOTS = {
    # S02 "Mossback's Loop": low at Tiny's height, trees towering like friendly giants, the sapling Tiny's equal
    "grove_s02_morning": dict(set="grove", tod="morning", water=0.85, haze=0.0012,
                              cam=((-3.4, -6.0, 0.3), (1.0, 2.0, 2.4), 22, 4.0), clear=[(-3.4, -6.0, 3.0)],
                              robots=[("tiny", -1.6, -4.4, ("cam", 40)), ("mossback", "loop", 70, ("cam", 75))]),
    # S07 "Amber Lights": the same master, days later, the drought showing
    "grove_s07_drought": dict(set="grove", tod="morning", water=0.12, haze=0.002,
                              cam=((-3.4, -6.0, 0.3), (1.0, 2.0, 2.4), 22, 4.0), clear=[(-3.4, -6.0, 3.0)],
                              robots=[("tiny", -1.6, -4.4, ("cam", 40))]),
    # S26 "Sunrise": low from the bent pipe as the sunrise comes down Grove Boulevard; the gauges turning green
    "grove_s26_sunrise": dict(set="grove", tod="sunrise", water=0.62, haze=0.0022, pipe=True,
                              cam=((9.6, 18.0, 0.6), (30.0, 6.0, 2.2), 24, 5.6), clear=[(9.6, 18.0, 3.0)],
                              robots=[("tiny", 12.4, 16.2, ("cam", -40))]),
    # S31 "Check... No Harm. Go.": wide on the fully green Grove: sapling, gauges, the bent pipe and blossom
    "grove_s31_golden": dict(set="grove", tod="golden_morning", water=1.0, haze=0.0007, pipe=True,
                             cam=((-13.0, -1.0, 3.4), (12.0, 10.0, 1.2), 24, None), clear=[(-13.0, -1.0, 5.0)],
                             robots=[("tiny", 0.8, -1.2, ("cam", 20)), ("mossback", "loop", 150, ("cam", 70))]),
    # ---- Main Square (local coordinates: the square centred on the origin, the Big Board east at x = 24.5)
    # S03 "The Fast Lane Pitch": wide in bright daylight from the crowd's knee height; Quota at the model table,
    # Shine over the stage, Warden at the edge, the Fast Lane on the Board
    "square_s03_day": dict(set="square", tod="day", lamps="off", board="fastlane", grove_water=0.85, haze=0.0008,
                           cam=((-27.0, -15.0, 7.5), (14.0, 0.5, 4.0), 24, None),
                           robots=[("quota", 4.6, -2.6, ("cam", 25)), ("shine", 19.6, 2.6, ("cam", 0), 2.4),
                                   ("warden", 11.0, -6.0, ("cam", 20)), ("tiny", -20.5, -13.0, ("cam", 30))]),
    # S03 reverse: from the top of the stage down Grove Boulevard to the Grove's treetops
    "square_s03_boulevard": dict(set="square", tod="day", lamps="off", board="fastlane", grove_water=0.85,
                                 haze=0.0008, cam=((21.0, 2.0, 4.2), (-118.0, 0.0, 5.0), 55, None), robots=[]),
    # S09 "A Villain for the Crowd": tense amber evening, the Grove's red gauges on the Board, a red wave of chest
    # lamps sweeping from the back toward the stage; Tiny on its crate lookout
    "square_s09_evening": dict(set="square", tod="evening", lamps="wave", wave=-4.0, board="grove_red",
                               grove_water=0.15, haze=0.0016,
                               cam=((15.5, -15.0, 3.2), (-14.0, 3.0, 2.0), 26, None),
                               robots=[("tiny", -16.7, -8.6, ("cam", 10), 2.15), ("quota", 4.6, -2.6, ("cam", 40)),
                                       ("shine", -2.0, 2.0, ("cam", 10), 3.4)]),
    # S17 "One Night": the split vote from overhead, a quilt of red and green lamps; Tiny and Warden on the top
    # platform, the vote on the Board
    "square_s17_overhead": dict(set="square", tod="dusk", lamps="mixed", board="vote", grove_water=0.15,
                                haze=0.0012, exposure=1.0, cam=((-8.0, -30.0, 32.0), (4.0, 0.0, 0.0), 28, None),
                                robots=[("tiny", 20.4, -0.4, -90, 1.8), ("warden", 20.4, -2.0, -90, 1.8)]),
    # ---- The Pipeworks (local coordinates: room |x| < 15, |y| < 11; panel at (0, 6.2) facing south)
    # S05 "The Lever": low at Tiny's height, the huge panel and lever above it, the blank wall square behind
    "pw_s05_afternoon": dict(set="pipeworks", mood="afternoon", lever="up", bent=True, tree_gauge=0.85,
                             haze=0.012, cam=((-2.4, -1.4, 0.32), (0.6, 6.2, 2.3), 20, 4.0),
                             robots=[("tiny", -0.5, 2.7, 200)]),
    # S12 "Behind the Wall": the dark, huge room; Tiny frozen at the lever, small, amber lamps the only light
    "pw_s12_wide": dict(set="pipeworks", mood="late_night", lever="down", bent=True, tree_gauge=0.1, nursery=1.0,
                        haze=0.02, cam=((-9.0, -8.5, 3.0), (0.6, 5.4, 2.0), 24, None),
                        robots=[("tiny", 1.45, 5.25, 180, 0.35)]),
    # S12: the cramped valve room behind the wall, lit only by the red tree gauge
    "pw_s12_valve": dict(set="pipeworks", mood="late_night", lever="down", bent=True, tree_gauge=0.1, haze=0.0,
                         cam=((1.5, 8.85, 0.3), (-0.6, 9.3, 0.45), 18, 2.8), rim=0.0,
                         robots=[("tiny", -0.75, 8.95, 125)]),
    # S19 "Every Logic a Job": five robots in a loose ring round the panel, Quota filling the doorway
    "pw_s19_night": dict(set="pipeworks", mood="night", lever="down", bent=True, tree_gauge=0.1, haze=0.014,
                         cam=((11.8, 4.2, 3.0), (-3.0, -3.2, 1.6), 20, None),
                         robots=[("ledger", 3.0, 4.8, ("cam", 10)), ("primly", -3.8, 2.8, 180),
                                 ("shine", -0.6, 1.4, ("cam", 0), 3.4), ("dash", 2.6, 2.4, ("cam", 35)),
                                 ("quota", 0.0, -9.6, ("cam", 0)), ("warden", -1.8, -1.6, ("cam", 25))]),
    # ---- The Rooftop Nursery (coordinates local to the roof: |x|, |y| < 10, the south edge looks over the Grove)
    # S04 "The Forgotten Nursery": the wide reveal of drooping rows, the tank looming, the Grove beyond the edge
    "nursery_s04_reveal": dict(set="nursery", tod="afternoon", water=0.0, grove_water=0.85, haze=0.0008,
                               cam=((9.2, 4.0, 2.6), (-4.0, -8.0, -1.4), 22, None),
                               robots=[("tiny", -2.0, -3.4, ("cam", 30))]),
    # S04: low at Tiny's height, the trays like long fields and the tank a cliff
    "nursery_s04_low": dict(set="nursery", tod="afternoon", water=0.0, grove_water=0.85, haze=0.0008,
                            cam=((-1.9, -7.4, 0.22), (-3.6, 6.0, 2.2), 18, 4.0),
                            robots=[("tiny", -1.8, -4.6, ("cam", 25))]),
    # S06 "Perking Up": the green ripple halfway down the rows; Tiny at the roof edge against the sunset
    "nursery_s06_sunset": dict(set="nursery", tod="sunset", water=0.55, grove_water=0.6, haze=0.0012,
                               cam=((1.0, -5.6, 4.6), (-1.0, -44.0, -19.0), 28, 8.0),
                               robots=[("tiny", 0.4, -9.45, 8)]),
    # S20 "Tanks Away": night, every row green and upright, Mossback and Dash by the carrying tanks
    "nursery_s20_night": dict(set="nursery", tod="night", water=1.0, grove_water=0.15, haze=0.004,
                              cam=((2.6, -1.8, 0.6), (-1.2, 5.0, 1.0), 20, None),
                              robots=[("mossback", -1.8, 3.4, ("cam", 60)), ("dash", 1.2, 4.6, ("cam", 40))]),
    # ---- The Junk Stacks (local coordinates: Tiny's crate at the origin, door and porch facing east; weed at
    # (2.6, 0.45); the gap toward the Grove to the north-east)
    # S01 "A Little Box in the Fog": wide and low, crate towers like mountains, Tiny's doorway the only warm light
    "junk_s01_wide": dict(set="junk", tod="dawn", haze=0.03, exposure=0.6, haze_color=(0.62, 0.7, 0.85),
                          cam=((9.5, -7.5, 0.55), (-1.0, 1.5, 3.2), 20, None),
                          robots=[("tiny", 0.78, 0.0, ("cam", 15), 0.05)]),
    # S01: Tiny's eye height at the weed
    "junk_s01_weed": dict(set="junk", tod="dawn", haze=0.03, exposure=0.5, haze_color=(0.62, 0.7, 0.85),
                          cam=((3.55, -0.75, 0.13), (2.45, 0.6, 0.12), 32, 2.8),
                          robots=[("tiny", 2.05, 0.85, ("cam", 55))]),
    # S14 "Thinking It Through": low on the porch, three scrap cubes in a row, the emblem plate behind
    "junk_s14_porch": dict(set="junk", tod="dawn", haze=0.035, exposure=0.5, haze_color=(0.6, 0.68, 0.84), skid=True, scraps=True,
                           cam=((2.1, -1.25, 0.32), (0.55, 0.35, 0.35), 26, 4.0),
                           robots=[("tiny", 0.64, 0.2, ("cam", 10), 0.05)]),
    # S30 "Around the Weed": warm morning, the S01 framing mirrored; Dash stopped a hand's width from the weed
    "junk_s30_morning": dict(set="junk", tod="morning", haze=0.004, skid=True,
                             cam=((2.3, -1.9, 0.16), (3.0, 0.7, 0.32), 28, 4.0),
                             robots=[("dash", 3.45, 0.45, -90), ("mossback", 9.0, 6.0, ("cam", 80))]),
    # ---- Fast Lane Works (Grove coordinates: the road runs along y = 0 and ends at x = -34.3, 2 m short of the
    # Grove's west wall and gate)
    # S08 "Already Finished": wide down the road, Quota parked at the end facing the drooping trees, Tiny in the gap
    "fl_s08_wide": dict(set="fastlane", tod="day", water=0.15, fast_lane="straight", haze=0.0009,
                        cam=((-74.0, -5.5, 2.4), (-30.0, 0.5, 2.0), 30, None),
                        robots=[("quota", -38.6, 0.0, 90, 0.35), ("dash", -45.0, -4.2, 30, 0.35),
                                ("tiny", -33.2, 0.6, -90, -0.15)]),
    # S08: from Tiny's height, the blade a wall across the top of the frame
    "fl_s08_low": dict(set="fastlane", tod="day", water=0.15, fast_lane="straight", haze=0.0009,
                       cam=((-32.9, 2.5, 0.02), (-37.0, -0.4, 1.5), 20, 4.0),
                       robots=[("tiny", -33.7, 0.9, ("cam", 60), -0.15), ("quota", -38.6, 0.0, 90, 0.35)]),
    # S21 "The Pipe Race": high wide at night, floodlight cones, the new pipe running off the road toward the Grove
    "fl_s21_night": dict(set="fastlane", tod="night", water=0.15, fast_lane="straight", pipe_line=True, haze=0.012,
                         cam=((-60.0, -22.0, 13.0), (-32.0, 1.0, 0.0), 28, None),
                         robots=[("quota", -24.0, 1.4, 90), ("dash", -40.0, -4.0, 60, 0.35), ("primly", -29.0, 3.6, 0),
                                 ("shine", -30.0, -0.5, 0, 4.5), ("warden", -47.0, 7.0, ("cam", 30), 0.35)]),
    # S27 "Around Is Faster": high top-down as the barriers form the curve, Quota's blade raised, Dash arriving
    "fl_s27_top": dict(set="fastlane", tod="morning", water=0.95, fast_lane="curve", haze=0.0006,
                       cam=((-50.0, -32.0, 54.0), (-40.0, -20.0, 0.0), 30, None),
                       robots=[("quota", -47.0, -21.0, 140, 0.35), ("dash", -36.0, -38.0, 90)]),
    # ---- The Foundry (local coordinates: hall |x| < 28, |y| < 19; the Press at x = -19, the great doors east)
    # S10 "The Sad Little Square": low from Tiny's height, Warden a pillar, the Press a cliff, the pen behind
    "fd_s10_night": dict(set="foundry", mood="night", pen_open=False, haze=0.01,
                         cam=((7.0, -7.5, 0.35), (-16.0, 3.0, 7.5), 20, None),
                         robots=[("warden", 2.4, -3.2, ("cam", 30)), ("tiny", 4.2, -4.9, ("cam", 35)),
                                 ("mossback", -4.0, 7.9, ("cam", 80))]),
    # S18 "The Order Does Not Say Where": wide and low from beside the Press toward the doors and the blue night;
    # the crate set down facing the Press, Warden at the open pen gate, Mossback leaving the pen
    "fd_s18_night": dict(set="foundry", mood="night", pen_open=True, crate=(-6.8, -3.4, "amber", 0.0, math.pi),
                         haze=0.01, cam=((-11.8, -5.8, 1.0), (24.0, 3.0, 3.5), 22, None),
                         robots=[("warden", 1.2, 8.6, ("cam", 40)), ("mossback", 3.0, 4.2, ("cam", 70))]),
    # S28 "The Honest Question": low and wide, the tiny crate under the towering Press, a gold bar of sunrise
    "fd_s28_crate": dict(set="foundry", mood="morning", pen_open=True, plate=True,
                         crate=(-12.2, 0.0, "amber", 0.0, math.pi), haze=0.0025,
                         cam=((-4.5, -5.5, 0.35), (-19.0, 0.5, 8.5), 18, None),
                         robots=[("warden", -10.6, 3.8, ("cam", 20))]),
    # S28: the crowd in the doors, a wall of silhouettes against the sunrise; Dash at the front, Shine over them
    "fd_s28_doors": dict(set="foundry", mood="morning", pen_open=True, plate=True, crowd=60,
                         crate=(-12.2, 0.0, "green", 0.0, math.pi), haze=0.0022,
                         cam=((-8.0, -3.5, 1.4), (28.0, 0.5, 4.0), 30, None),
                         robots=[("dash", 25.0, -0.5, -90), ("shine", 22.0, 2.5, -90, 4.0),
                                 ("ledger", -7.0, -8.6, ("cam", 20))]),
    # ---- The Count House (local coordinates: hall |x| < 13, |y| < 8; main aisle along x, the screen on the west wall)
    # S11 "Count: Footsteps, Two": from Tiny's eye level, Ledger towering, the reading screen big behind them
    "ch_s11_low": dict(set="counthouse", mood="night", screen="footprints", ladder_x=3.0, dusty=True, haze=0.006,
                       cam=((-2.6, -0.75, 0.3), (-10.5, 0.4, 3.2), 20, None),
                       robots=[("ledger", -7.4, 0.55, ("cam", 15)), ("tiny", -8.6, -0.5, 80, 0.3)]),
    # S11: a wide down the aisle, Tiny a speck at the foot of the shelves, Ledger up on the ladder
    "ch_s11_wide": dict(set="counthouse", mood="night", screen="bars", ladder_x=-2.0, haze=0.006,
                        cam=((12.4, 0.0, 6.0), (-8.0, 0.2, 1.4), 24, None),
                        robots=[("tiny", 3.0, -0.2, ("cam", 20)), ("ledger", -2.0, 0.55, ("cam", 0), 3.3)]),
    # S29 "A New Drawer": morning sun through the high window lying in a gold bar along the aisle
    "ch_s29_morning": dict(set="counthouse", mood="morning", screen="footprints_faint", ladder_x=10.4,
                           green_handle=True, haze=0.008,
                           cam=((-11.2, -0.5, 1.5), (10.0, 0.3, 2.6), 24, None),
                           robots=[("ledger", 10.0, 0.3, ("cam", 10))]),
    # S29: the last shot: one green handle among hundreds of amber ones, gold light on the floor
    "ch_s29_handle": dict(set="counthouse", mood="morning", screen="off", ladder_x=6.0, green_handle=True,
                          haze=0.006, cam=((5.6, -1.0, 1.3), (11.2, 1.1, 0.5), 28, None),
                          robots=[("ledger", 10.4, -0.7, ("cam", 40))]),
}


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = opts.get("device", "HIP")
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = d.type != "CPU"
    sc.cycles.device = "GPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 3
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.render.resolution_x, sc.render.resolution_y = RES
    if "preview" in opts:
        sc.render.resolution_percentage = 40
    sc.render.image_settings.file_format = "PNG"
    sc.frame_set(1)
    return sc


def camera(sc, loc, target, lens, fstop):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 2000
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
    sc.camera = cam
    return cam


def place(sc, rid, x, y, yaw, cam, z=0.0):
    spec = json.loads((CAST / f"{rid}.json").read_text(encoding="utf-8"))
    root = robot.build(spec, None, (x, y, z))
    if isinstance(yaw, tuple):            # face the camera, then turn by an offset
        to_cam = cam.location - Vector((x, y, z))
        face = math.atan2(-to_cam.x, to_cam.y) + math.pi    # front is -Y: yaw so that (sin, -cos) points at it
        root.rotation_euler.z = face + math.radians(yaw[1])
    else:
        root.rotation_euler.z = math.radians(yaw)
    bpy.context.view_layer.update()
    return root, spec


def seen(sc, cam, point):
    """True when the point is inside the frame and nothing stands between it and the camera."""
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(sc, cam, Vector(point))
    if not (0.08 < v.x < 0.92 and 0.05 < v.y < 0.95 and v.z > 0):
        return False
    dg = bpy.context.evaluated_depsgraph_get()
    d = Vector(point) - cam.location
    hit, loc, *_ = sc.ray_cast(dg, cam.location, d.normalized(), distance=d.length - 0.6)
    return not hit


def shoot(name):
    sh = SHOTS[name]
    sc = setup()
    if sh["set"] == "square":
        parts = mainsquare.build(sc, tod=sh["tod"], lamps=sh.get("lamps", "off"), board=sh.get("board", "fastlane"),
                                 grove_water=sh.get("grove_water", 0.85), wave=sh.get("wave"))
    elif sh["set"] == "nursery":
        parts = nursery.build(sc, tod=sh["tod"], water=sh["water"], grove_water=sh.get("grove_water", 0.85))
        ox, oy, oz = nursery.ORIGIN
        loc, tgt, lens, fs = sh["cam"]
        sh = dict(sh, cam=((loc[0] + ox, loc[1] + oy, loc[2] + oz), (tgt[0] + ox, tgt[1] + oy, tgt[2] + oz), lens, fs),
                  robots=[(r[0], r[1] + ox, r[2] + oy, r[3], (r[4] if len(r) > 4 else 0.0) + oz) for r in sh["robots"]])
    elif sh["set"] == "fastlane":
        parts = grove.build(sc, tod=sh["tod"], water=sh["water"], fast_lane=sh.get("fast_lane", "straight"),
                           pipe_line=sh.get("pipe_line", False))
    elif sh["set"] == "counthouse":
        parts = counthouse.build(sc, mood=sh["mood"], screen=sh.get("screen", "off"), ladder_x=sh.get("ladder_x", 0.0),
                                 dusty=sh.get("dusty", False), green_handle=sh.get("green_handle", False))
    elif sh["set"] == "foundry":
        parts = foundry.build(sc, mood=sh["mood"], pen_open=sh.get("pen_open", False), crowd_n=sh.get("crowd", 0),
                              plate=sh.get("plate", False),
                              crate=(sh["crate"][0], sh["crate"][1], sh["crate"][2], sh["crate"][3], sh["crate"][4])
                              if sh.get("crate") else None)
    elif sh["set"] == "junk":
        parts = junk.build(sc, tod=sh["tod"], skid=sh.get("skid", False), scraps=sh.get("scraps", False))
    elif sh["set"] == "pipeworks":
        parts = pipeworks.build(sc, mood=sh["mood"], lever=sh.get("lever", "down"), bent=sh.get("bent", True),
                                tree_gauge=sh.get("tree_gauge", 0.5), nursery=sh.get("nursery", 1.0))
    else:
        parts = grove.build(sc, tod=sh["tod"], water=sh["water"], pipe=sh.get("pipe", False),
                           clear=sh.get("clear", []))
    cam = camera(sc, *sh["cam"])
    bpy.context.view_layer.update()
    roots = []
    for entry in sh["robots"]:
        rid, x, y, yaw = entry[:4]
        z = entry[4] if len(entry) > 4 else 0.0
        if x == "loop":
            for k in range(60):
                a = math.radians(y + 6 * k)
                px, py = math.cos(a) * grove.LOOP_R, math.sin(a) * grove.LOOP_R
                far = (Vector((px, py, 0)) - cam.location).length > 7.0
                if far and seen(sc, cam, (px, py, 0.8)) and seen(sc, cam, (px, py, 0.25)):
                    break
            else:
                print("no clear view of", rid, "on the loop", flush=True)
            x, y = px, py
        roots.append(place(sc, rid, x, y, yaw, cam, z))
    if sh["cam"][3]:
        # focus on the first robot
        r0 = roots[0][0]
        lo, hi = robot.bounds(r0)
        cam.data.dof.focus_distance = (cam.location - (lo + hi) / 2).length
    if sh["set"] == "pipeworks":
        if sh.get("haze", 0) > 0 and "nohaze" not in opts:
            look.atmosphere(sc, density=sh["haze"], color=(0.9, 0.88, 0.84), anisotropy=0.6, centre=(0, -1.0, 0),
                            size=(29.6, 19.6, 11.8))
    elif sh["set"] == "counthouse":
        look.atmosphere(sc, density=sh.get("haze", 0.006), color=(0.95, 0.85, 0.72), anisotropy=0.6, centre=(0, 0, 0),
                        size=(25.6, 15.6, 13.8))
    elif sh["set"] == "foundry":
        look.atmosphere(sc, density=sh.get("haze", 0.01), color=(0.95, 0.88, 0.8), anisotropy=0.6, centre=(0, 0, 0),
                        size=(55.6, 37.6, 19.8))
    else:
        # the haze box must contain the camera: seen from above, its top face reads as a dark band
        top = max(18.0, sh["cam"][0][2] + 12.0)
        look.atmosphere(sc, density=sh.get("haze", 0.0015), color=sh.get("haze_color", (0.98, 0.92, 0.84)),
                        anisotropy=0.75, centre=(-40 if sh["set"] == "square" else 0, 0, 0), size=(380, 380, top))
    look.grade(sc)
    sc.view_settings.exposure = sh.get("exposure", 0.0)
    for (r, spec) in roots:
        lo, hi = robot.bounds(r)
        if sh.get("rim", 0.8) > 0:
            look.rim(sc, r, hi.z - lo.z, sh.get("rim", 0.8))
    sc.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("shot", name, "->", sc.render.filepath, flush=True)


for a in args[1:]:
    shoot(a)
