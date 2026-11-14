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


# ------------------------------------------------------------------ scene
def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "HIP"
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = d.type != "CPU"
    sc.cycles.device = "GPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
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
    """Dark studio floor and back wall, scaled to the subject height h."""
    mat = materials.make({"id": "stage", "kind": "painted_metal", "color": "#2b3038", "roughness": 0.55,
                          "wear": 0.15, "dirt": 0.35, "tex_tile": max(0.4, h * 0.8)})
    size = h * 40
    floor = robot.mesh_box("stage_floor", (size, size, h * 0.05), "box", sc.collection, mat, 0)
    floor.location = (0, 0, -h * 0.025)
    wall = robot.mesh_box("stage_wall", (size, h * 0.05, size * 0.5), "box", sc.collection, mat, 0)
    wall.location = (0, h * 5, size * 0.25)


def light(sc, name, kind, loc, target, energy, size=1.0, color=(1, 1, 1), spot=40):
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
    return ob


def rig(sc, h, centre):
    """Key spot from above-front, warm fill, cool rim: a pool of light on a dark stage."""
    c = Vector(centre)
    key = light(sc, "key", "SPOT", c + Vector((-1.2, -2.2, 3.4)) * h, c, 900 * h * h, 0.35 * h, (1.0, 0.95, 0.86), 38)
    fill = light(sc, "fill", "AREA", c + Vector((2.4, -2.0, 1.0)) * h, c, 60 * h * h, 2.0 * h, (1.0, 0.82, 0.62))
    rim = light(sc, "rim", "AREA", c + Vector((1.0, 2.6, 2.4)) * h, c, 260 * h * h, 1.2 * h, (0.55, 0.8, 1.0))
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
    if MODE == "lineup":
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
        dist = max(h / (0.44 * 2 * tv), wid / 0.76 / 2 / th)
        c = Vector((0, 0, h * 0.5 + 0.16 * 2 * dist * tv))
        cam = camera(sc, c, dist, h * 0.05, 18, lens)
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
    if "stills" in opts:              # check a few frames before a full render
        for f in [int(v) for v in opts["stills"].split(",")]:
            sc.frame_set(f)
            sc.render.filepath = str(OUT / f"still_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
        return
    sc.frame_set(1)
    bpy.ops.render.render(animation=True)
    print("rendered", MODE, FRAMES, "frames ->", OUT, flush=True)


main()
