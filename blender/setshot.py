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
import mainsquare  # noqa: E402
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
    look.atmosphere(sc, density=sh.get("haze", 0.0015), color=(0.98, 0.92, 0.84), anisotropy=0.75,
                    centre=(-40 if sh["set"] == "square" else 0, 0, 0), size=(380, 380, 18))
    look.grade(sc)
    sc.view_settings.exposure = sh.get("exposure", 0.0)
    for (r, spec) in roots:
        lo, hi = robot.bounds(r)
        look.rim(sc, r, hi.z - lo.z, 0.8)
    sc.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("shot", name, "->", sc.render.filepath, flush=True)


for a in args[1:]:
    shoot(a)
