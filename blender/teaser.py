"""Teaser shots: one robot entering a pool of light on a dark stage, or the whole cast lined up (9:16).

  blender -b --factory-startup -P blender/teaser.py -- <out_dir> <mode> <spec.json> [<spec.json> ...]
        [--frames N] [--samples S] [--res 1080x1920] [--preview]

modes:
  intro   one robot enters (rolls / walks / hops / hovers by its locomotion), settles, blinks, looks around
  hook    the Tiny Robot in the dark; its eyes blink on, then a light fades up
  lineup  every robot side by side, slow push-in
Frames are written as <out_dir>/####.png. Text is added later, in post.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import materials  # noqa: E402
import robot  # noqa: E402
import world  # noqa: E402
import look  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
opts, pos = {}, []
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
        pos.append(argv[i])
        i += 1
OUT, MODE = Path(pos[0]), pos[1]
SPECS = [json.loads(Path(p).read_text(encoding="utf-8")) for p in pos[2:]]
FPS = 30
FRAMES = int(opts.get("frames", 96))
RES = tuple(int(v) for v in opts.get("res", "1080x1920").split("x"))
SAMPLES = int(opts.get("samples", 48))
LANDSCAPE = RES[0] > RES[1]


# ------------------------------------------------------------------ scene
def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = opts.get("device", "HIP")     # HIP on the local AMD card, OPTIX on NVIDIA
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = d.type != "CPU"
    sc.cycles.device = "GPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    # speed: keep the scene between frames, sensible bounce limits, no caustics, stop early on clean pixels
    sc.render.use_persistent_data = True
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.render.resolution_x, sc.render.resolution_y = RES
    if "preview" in opts:
        sc.render.resolution_percentage = 40
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, FRAMES
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(OUT) + "/"
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.4
    w = bpy.data.worlds.new("night")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.012, 0.016, 0.026, 1)
    bg.inputs["Strength"].default_value = 1.0
    sc.world = w
    return sc


def stage(sc, h):
    """The set: Gridhaven's square at blue hour (or, with --noworld, a dark studio floor and wall)."""
    if "noworld" not in opts:
        if not bpy.data.collections.get("gridhaven"):
            world.build(sc, seed=int(opts.get("seed", 7)), tod=opts.get("time", "dusk"))
        return
    mat = materials.make({"id": "stage", "kind": "painted_metal", "color": "#2b3038", "roughness": 0.55,
                          "wear": 0.15, "dirt": 0.35, "tex_tile": max(0.4, h * 0.8)})
    size = h * 40
    floor = robot.mesh_box("stage_floor", (size, size, h * 0.05), "box", sc.collection, mat, 0)
    floor.location = (0, 0, -h * 0.025)
    wall = robot.mesh_box("stage_wall", (size, h * 0.05, size * 0.5), "box", sc.collection, mat, 0)
    wall.location = (0, h * 5, size * 0.25)


def light(sc, name, kind, loc, target, energy, size=1.0, color=(1, 1, 1), spot=40, scatter=False):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    if kind == "SPOT":
        ld.spot_size = math.radians(spot)
        ld.spot_blend = 0.6
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    ob.visible_volume_scatter = scatter      # only motivated sources (lamps, the key spot) light the haze
    return ob


def rig(sc, h, centre):
    """Key spot from above-front, warm fill, cool rim: a pool of light on a dark stage."""
    c = Vector(centre)
    k = world.CFG.get("rig", 1.0) if "noworld" not in opts else 1.0
    key = light(sc, "key", "SPOT", c + Vector((-1.2, -2.2, 3.4)) * h, c, 900 * h * h * k, 0.35 * h, (1.0, 0.95, 0.86), 38,
                scatter=True)
    fill = light(sc, "fill", "AREA", c + Vector((2.4, -2.0, 1.0)) * h, c, 60 * h * h * k, 2.0 * h, (1.0, 0.82, 0.62))
    rim = light(sc, "rim", "AREA", c + Vector((1.0, 2.6, 2.4)) * h, c, 260 * h * h * k, 1.2 * h, (0.55, 0.8, 1.0))
    return key, fill, rim


def camera(sc, target, dist, height, yaw_deg, lens):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 36.0          # framing maths below assumes a 36 mm sensor on the fitted side
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 2.8
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    a = math.radians(yaw_deg)
    cam.location = Vector(target) + Vector((math.sin(a) * dist, -math.cos(a) * dist, height))
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    focus = bpy.data.objects.new("focus", None)
    sc.collection.objects.link(focus)
    focus.location = target
    cd.dof.focus_object = focus
    sc.camera = cam
    return cam


# ------------------------------------------------------------------ animation helpers
def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def joints(root, role):
    return [o for o in root.children_recursive if o.get("role") == role and o.type == "EMPTY"]


def eyes(root):
    return [o for o in root.children_recursive if o.get("role") == "eye"]


REST = {}


def key_eye(root, f, **vals):
    """Key an expression; with no values the eyes go back to the robot's resting expression."""
    for e in eyes(root):
        rest = REST.setdefault(e.name, {kb.name: kb.value for kb in e.data.shape_keys.key_blocks[1:]})
        for kb in e.data.shape_keys.key_blocks[1:]:
            kb.value = vals.get(kb.name, 0.0) if vals else rest.get(kb.name, 0.0)
            kb.keyframe_insert("value", frame=f)


def blink(root, f):
    key_eye(root, f - 2)
    key_eye(root, f, blink=1.0)
    key_eye(root, f + 3)


def animate_intro(spec, root, h):
    loco = spec.get("locomotion", "walk")
    rest = root.location.copy()
    enter_f = 30
    base_rot = {o.name: o.rotation_euler.copy() for o in root.children_recursive if o.type == "EMPTY"}
    for f in range(1, FRAMES + 1):
        t = ease((f - 1) / enter_f)
        p = rest.copy()
        if loco == "hover":
            p.z += (1 - t) * h * 1.4 + math.sin(f * 0.12) * h * 0.02
        else:
            p.x += -(1 - t) * h * 2.6
        if loco == "hop":
            hop = abs(math.sin((f - 1) / enter_f * math.pi * 3)) * h * 0.35 * (1 - t)
            p.z += hop
        root.location = p
        root.keyframe_insert("location", frame=f)
        speed = (1 - t) * 3.0
        for w in joints(root, "wheel"):
            w.rotation_euler.x = base_rot[w.name].x - (1 - t) * 6.0
            w.keyframe_insert("rotation_euler", frame=f)
        for side, ph in (("foot_l", 0), ("foot_r", math.pi)):
            for ft in joints(root, side):
                lift = max(0.0, math.sin(f * 0.5 + ph)) * h * 0.04 * min(1.0, speed)
                ft.delta_location = (0, 0, lift)
                ft.keyframe_insert("delta_location", frame=f)
        for body in joints(root, "body") or joints(root, "head"):
            body.delta_location = (0, 0, math.sin(f * 0.16) * h * 0.008)
            body.keyframe_insert("delta_location", frame=f)
    # face: look around after arriving, blink, end happy
    key_eye(root, 1)
    blink(root, enter_f + 8)
    for e in (o for o in root.children_recursive if o.get("role") == "eyes"):
        x0 = e.location.x
        for f, dx in ((enter_f + 14, 0), (enter_f + 22, -1), (enter_f + 34, 1), (enter_f + 44, 0)):
            e.location.x = x0 + dx * spec["face"]["screen"][0] * 0.12
            e.keyframe_insert("location", frame=f)
    key_eye(root, FRAMES - 22)
    key_eye(root, FRAMES - 14, happy=1.0)


def animate_hook(root, key_lights):
    key_eye(root, 1, blink=1.0)
    key_eye(root, 30, blink=1.0)
    key_eye(root, 36)
    blink(root, 70)
    for lt in key_lights:
        e = lt.data.energy
        lt.data.energy = 0.0
        lt.data.keyframe_insert("energy", frame=40)
        lt.data.energy = e
        lt.data.keyframe_insert("energy", frame=80)


# ------------------------------------------------------------------ shots
def fit_row(sc, cam, roots, aim, x_lo, x_hi, push=1.0):
    """Measure the robots' projected extent and adjust camera distance and lens shift until the row spans
    x_lo..x_hi of the frame (checked at the end of the push-in, where it is tightest)."""
    from bpy_extras.object_utils import world_to_camera_view
    corners = []
    dg = bpy.context.evaluated_depsgraph_get()
    for r in roots:
        for ob in r.children_recursive:
            if ob.type == "MESH":
                corners += [ob.matrix_world @ Vector(c) for c in ob.evaluated_get(dg).bound_box]
    for _ in range(4):
        start = cam.location.copy()
        cam.location = aim + (start - aim) * push
        bpy.context.view_layer.update()
        xs = [world_to_camera_view(sc, cam, c).x for c in corners]
        cam.location = start
        span, want = max(xs) - min(xs), x_hi - x_lo
        cam.location = aim + (cam.location - aim) * (span / want)
        cam.data.shift_x += ((min(xs) + max(xs)) / 2 - 0.5) * (span / want)
        bpy.context.view_layer.update()


def place_line(specs):
    roots, x = [], 0.0
    tallest = max(s.get("height_m", 1) for s in specs)
    for s in specs:
        r = robot.build(s)
        bpy.context.view_layer.update()
        lo, hi = robot.bounds(r)
        r.location.x += x - lo.x
        x += (hi.x - lo.x) + tallest * 0.12
        roots.append(r)
    total = x - tallest * 0.12
    for r in roots:
        r.location.x -= total / 2
    bpy.context.view_layer.update()
    return roots, total, tallest


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sc = setup()
    if MODE == "lineup" and LANDSCAPE:
        # 16:9: the classic side-by-side lineup at true scale, tallest on the left
        roots, width, h = place_line(sorted(SPECS, key=lambda s: -s.get("height_m", 1)))
        # stagger in depth and turn each a little toward camera, so the row has rhythm instead of a parade line
        for k, r in enumerate(roots):
            r.location.y += (0.0, 0.9, -0.4, 0.6, -0.2, 0.7, -0.3, 0.2)[k % 8]
            r.rotation_euler.z = math.radians(-12 + (k % 3) * 6)
        # foreground props for depth
        fg = materials.make({"id": "fg_crate", "kind": "painted_metal", "color": "#8a5a3c", "wear": 0.6, "dirt": 0.6,
                             "tex_tile": 0.8})
        for (fx, fy, fs) in ((-width * 0.55, -3.2, 0.9), (-width * 0.55 + 1.0, -3.0, 0.6), (width * 0.5, -2.6, 0.7)):
            robot.mesh_box("fg_crate", (fs, fs, fs), "box", sc.collection, fg, 0.03).location = (fx, fy, fs / 2)
        bpy.context.view_layer.update()
        stage(sc, 1.6)
        mid = Vector((0, 0, h * 0.45))
        rig(sc, max(h, 2.2) * 1.4, mid)
        kk = world.CFG.get("rig", 1.0)
        light(sc, "top", "AREA", mid + Vector((0, -1.5, 7.0)), mid, 4200 * kk, 9.0, (1.0, 0.96, 0.9))
        light(sc, "front", "AREA", mid + Vector((0, -12.0, 2.5)), mid, 2200 * kk, 8.0, (0.9, 0.95, 1.0))
        lens = 40
        vfov = 2 * math.atan(36 / 2 / lens)
        hfov = 2 * math.atan(math.tan(vfov / 2) * RES[0] / RES[1])
        dist = max(width / 0.84 / 2 / math.tan(hfov / 2), h / 0.5 / 2 / math.tan(vfov / 2))
        aim = mid + Vector((0, 0, 0.12 * 2 * dist * math.tan(vfov / 2)))
        cam = camera(sc, aim, dist, 0.35, 16, lens)          # low three-quarter view
        cam.data.dof.aperture_fstop = 5.6
        fit_row(sc, cam, roots, aim, 0.06, 0.94, push=0.92)
        start = cam.location.copy()
        for f in (1, FRAMES):
            cam.location = aim + (start - aim) * (1.0 if f == 1 else 0.92)
            cam.keyframe_insert("location", frame=f)
        for k, r in enumerate(roots):
            key_eye(r, 1)
            blink(r, 18 + (k * 13) % 50)
            key_eye(r, FRAMES - 40)
            key_eye(r, FRAMES - 32, happy=1.0)
    elif MODE == "lineup":
        # 9:16 group shot: tallest at the back, rows getting smaller toward the camera, the Tiny Robot in front
        layout = {"quota": (0.0, 3.4), "shine": (-2.7, 2.3), "warden": (2.5, 2.2), "primly": (-1.5, 0.9),
                  "ledger": (1.5, 0.9), "mossback": (-1.0, -0.5), "dash": (1.1, -0.6), "tiny": (0.0, -1.6)}
        roots = []
        for sp in SPECS:
            r = robot.build(sp)
            x, y = layout.get(sp["id"], (0.0, 0.0))
            r.location = (x, y, 0)
            r.rotation_euler.z = math.atan2(x, 9.0) * -1.0      # turn a little toward the camera
            roots.append(r)
        bpy.context.view_layer.update()
        lo = Vector((1e9,) * 3)
        hi = -lo
        for r in roots:
            a, b = robot.bounds(r)
            lo, hi = Vector(map(min, lo, a)), Vector(map(max, hi, b))
        h = hi.z - lo.z
        stage(sc, 1.6)
        mid = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, h * 0.4))
        rig(sc, max(h, 2.2) * 1.4, mid)
        light(sc, "top", "AREA", mid + Vector((0, -1.5, 7.0)), mid, 4200, 7.0, (1.0, 0.96, 0.9))
        light(sc, "front", "AREA", mid + Vector((0, -9.0, 2.5)), mid, 1600, 6.0, (0.9, 0.95, 1.0))
        lens = 40
        vfov = 2 * math.atan(36 / 2 / lens)
        hfov = 2 * math.atan(math.tan(vfov / 2) * RES[0] / RES[1])
        dist = max((hi.x - lo.x) / 0.92 / 2 / math.tan(hfov / 2), h / 0.5 / 2 / math.tan(vfov / 2)) + (hi.y - lo.y) / 2
        aim = mid + Vector((0, 0, 0.16 * 2 * dist * math.tan(vfov / 2)))
        cam = camera(sc, aim, dist, 1.0, 0, lens)
        cam.data.dof.aperture_fstop = 8
        start = cam.location.copy()
        for f in (1, FRAMES):
            cam.location = aim + (start - aim) * (1.0 if f == 1 else 0.9)
            cam.keyframe_insert("location", frame=f)
        for k, r in enumerate(roots):
            key_eye(r, 1)
            blink(r, 18 + (k * 13) % 50)
            key_eye(r, FRAMES - 40)
            key_eye(r, FRAMES - 32, happy=1.0)
    else:
        spec = SPECS[0]
        root = robot.build(spec)
        bpy.context.view_layer.update()
        lo, hi = robot.bounds(root)
        h = hi.z - lo.z
        w = max(hi.x - lo.x, hi.y - lo.y)
        stage(sc, max(h, 0.6))
        c = Vector((0, 0, h * 0.5))
        key, fill, rim = rig(sc, max(h, w * 0.8), c)
        # portrait frame: fit height with room for captions above and below
        lens = 50
        vfov = 2 * math.atan(36 / 2 / lens)                      # sensor fitted vertically
        hfov = 2 * math.atan(math.tan(vfov / 2) * RES[0] / RES[1])
        wid = max(hi.x - lo.x, hi.y - lo.y) * 1.05
        tv, th = math.tan(vfov / 2), math.tan(hfov / 2)
        # the robot fills the frame from 12% to 56% of its height (no more than 76% of its width): the bottom 10%
        # stays clear for platform UI and the top is free for the robot's name and logic
        if LANDSCAPE:
            # 16:9: the robot fills 14%-80% of the height on the right half; the left is for the captions
            dist = max(h / (0.6 * 2 * tv), wid / 0.46 / 2 / th)
            c = Vector((0, 0, h * 0.5 + 0.03 * 2 * dist * tv))
        else:
            dist = max(h / (0.40 * 2 * tv), wid / 0.70 / 2 / th)
            c = Vector((0, 0, h * 0.5 + 0.16 * 2 * dist * tv))
        cam = camera(sc, c, dist, h * 0.05, 18, lens)
        if LANDSCAPE:
            # put the robot's centre at 70% of the frame width by solving the lens shift (shift is linear in
            # screen position, so two projections are enough)
            from bpy_extras.object_utils import world_to_camera_view
            target = Vector((0, 0, h * 0.5))
            bpy.context.view_layer.update()
            x0 = world_to_camera_view(sc, cam, target).x
            cam.data.shift_x = -0.1
            bpy.context.view_layer.update()
            x1 = world_to_camera_view(sc, cam, target).x
            cam.data.shift_x = -0.1 * (0.70 - x0) / (x1 - x0)
        cam.data.dof.focus_object.location = Vector((0, 0, h * 0.5))
        start = cam.location.copy()
        for f in (1, FRAMES):          # slow push-in
            cam.location = c + (start - c) * (1.0 if f == 1 else 0.9)
            cam.keyframe_insert("location", frame=f)
        if MODE == "hook":
            animate_hook(root, [key, fill])
            rim.data.energy *= 0.3
        else:
            animate_intro(spec, root, h)
    if "nolook" not in opts:
        tod = opts.get("time", "dusk")
        haze = {"dusk": (0.012, (0.62, 0.7, 0.85), 0.55), "night_rain": (0.02, (0.72, 0.76, 0.86), 0.6),
                "night": (0.014, (0.72, 0.76, 0.86), 0.6),
                "morning": (0.0012, (0.98, 0.92, 0.84), 0.75)}[tod]
        # haze only near the street, so the sky above the rooftops stays clean
        look.atmosphere(sc, density=float(opts.get("haze", haze[0])), color=haze[1], anisotropy=haze[2],
                        centre=(0, 60, 0), size=(320, 320, 16 if tod == "morning" else 22))
        cam_ob = sc.camera
        aim = (cam_ob.matrix_world.to_3x3() @ Vector((0, 0, -1))) * 6 + cam_ob.location
        tgt = (robot.bounds(roots[0] if MODE == "lineup" else root)[0] +
               robot.bounds(roots[0] if MODE == "lineup" else root)[1]) / 2 if MODE != "lineup" else aim
        world.rain(sc, cam_ob, tgt)
        look.grade(sc)
        targets = roots if MODE == "lineup" else [root]
        for r in targets:
            lo_r, hi_r = robot.bounds(r)
            look.rim(sc, r, hi_r.z - lo_r.z, 0.6 if MODE == "lineup" else 1.0)
    if "stills" in opts:              # check a few frames before a full render
        for f in [int(v) for v in opts["stills"].split(",")]:
            sc.frame_set(f)
            sc.render.filepath = str(OUT / f"still_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
        return
    if "start" in opts:                # resume a stopped shot from its first missing frame
        sc.frame_start = int(opts["start"])
    sc.frame_set(sc.frame_start)
    bpy.ops.render.render(animation=True)
    print("rendered", MODE, FRAMES, "frames ->", OUT, flush=True)


main()
