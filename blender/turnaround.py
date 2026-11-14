"""Studio review renders of robot specs (Cycles, GPU).

  blender -b --factory-startup -P blender/turnaround.py -- <out_dir> <spec.json> [<spec.json> ...] [--samples N] [--size PX]
            [--only views|faces|lineup]

Writes per robot: <id>_turn.png (front, 3/4, side, back in one strip) and <id>_faces.png (expressions),
and lineup.png with every robot side by side for scale.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robot  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
opts = {}
files = []
i = 0
while i < len(argv):
    if argv[i].startswith("--"):
        opts[argv[i][2:]] = argv[i + 1]
        i += 2
    else:
        files.append(argv[i])
        i += 1
OUT = Path(files[0])
OUT.mkdir(parents=True, exist_ok=True)
SPECS = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files[1:]]
SAMPLES = int(opts.get("samples", 96))
SIZE = int(opts.get("size", 900))
ONLY = opts.get("only", "")


def reset():
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
    sc.view_settings.look = opts.get("look", "AgX - Punchy")
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("studio")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.32, 0.34, 0.37, 1)
    bg.inputs["Strength"].default_value = 0.35
    sc.world = world
    return sc


def studio(sc, h):
    """Cyclorama + three soft lights, all scaled to the subject height h."""
    import materials
    floor_mat = materials.make({"id": "cyc", "kind": "plastic", "color": "#8d9196", "roughness": 0.9,
                                "wear": 0.0, "dirt": 0.0})
    size = h * 30
    cyc = robot.mesh_box("cyc_floor", (size, size, h * 0.05), "box", sc.collection, floor_mat, 0)
    cyc.location = (0, 0, -h * 0.025)
    wall = robot.mesh_box("cyc_wall", (size, h * 0.05, size * 0.6), "box", sc.collection, floor_mat, 0)
    wall.location = (0, h * 3.2, size * 0.3)

    def area(name, loc, energy, size_, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy * h * h * 2.2
        ld.size = size_ * h
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(ob)
        ob.visible_camera = False
        ob.visible_glossy = False
        ob.location = Vector(loc) * h
        d = Vector((0, 0, h * 0.5)) - ob.location
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return ob

    area("key", (-2.2, -2.6, 2.6), 260, 1.6, (1.0, 0.96, 0.9))
    area("fill", (2.8, -1.8, 1.2), 70, 2.4, (0.85, 0.92, 1.0))
    area("rim", (1.2, 2.6, 2.4), 220, 1.0, (0.9, 0.95, 1.0))


def camera(sc, target, dist, height, yaw_deg, lens=70):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    a = math.radians(yaw_deg)
    cam.location = Vector(target) + Vector((math.sin(a) * dist, -math.cos(a) * dist, height))
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    return cam


def fit_dist(h, w, lens, aspect=1.0, margin=1.25):
    fov = 2 * math.atan(36 / 2 / lens)
    need = max(w, h * aspect) * margin   # Blender fits the 36 mm sensor to the wider side
    return need / 2 / math.tan(fov / 2) + w / 2


def render(sc, path, res=(SIZE, SIZE)):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def strip(paths, out):
    """Paste equal-size renders side by side (Blender's own image API, no PIL)."""
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    import numpy as np
    canvas = np.zeros((h, w * len(imgs), 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        canvas[:, k * w:(k + 1) * w] = px
    res = bpy.data.images.new("strip", w * len(imgs), h, alpha=True)
    res.pixels = canvas.ravel()
    res.filepath_raw = str(out)
    res.file_format = "PNG"
    res.save()
    for p in paths:
        Path(p).unlink()


def set_face(root, key, value=1.0):
    for ob in root.children_recursive:
        if ob.get("role") == "eye" and ob.data.shape_keys:
            for kb in ob.data.shape_keys.key_blocks[1:]:
                kb.value = value if kb.name == key else 0.0


for spec in SPECS:
    if ONLY == "lineup":
        break
    sc = reset()
    root = robot.build(spec)
    bpy.context.view_layer.update()
    lo, hi = robot.bounds(root)
    h = hi.z - lo.z
    w = max(hi.x - lo.x, hi.y - lo.y)
    studio(sc, h)
    centre = (lo + hi) / 2
    lens = 70
    dist = fit_dist(h, w, lens)
    if ONLY in ("", "views"):
        shots = []
        camera(sc, centre, dist, h * 0.12, 0, lens)
        for k, yaw in enumerate((0, -35, -90, 180)):   # turn the robot, keep camera and lights fixed
            root.rotation_euler.z = math.radians(yaw)
            p = OUT / f"_{spec['id']}_{k}.png"
            render(sc, p)
            shots.append(p)
        strip(shots, OUT / f"{spec['id']}_turn.png")
    face = spec.get("face")
    if face and ONLY in ("", "faces"):
        head = bpy.data.objects[f"{spec['id']}:{face['part']}.mesh"]
        hc = head.matrix_world.translation
        hs = max(head.dimensions)
        shots = []
        root.rotation_euler.z = 0
        bpy.context.view_layer.update()
        hc = head.matrix_world.translation
        for key in ("neutral", "blink", "happy", "sad", "angry", "wide"):
            set_face(root, key)
            camera(sc, hc, hs * 3.2, hs * 0.1, 12, 85)
            p = OUT / f"_{spec['id']}_f{key}.png"
            render(sc, p, (SIZE // 2, SIZE // 2))
            shots.append(p)
        set_face(root, "neutral")
        root.rotation_euler.z = 0
        strip(shots, OUT / f"{spec['id']}_faces.png")
    print(f"done {spec['id']}", flush=True)

if len(SPECS) > 1 and ONLY in ("", "lineup"):
    sc = reset()
    x = 0.0
    roots = []
    tallest = max(s.get("height_m", 1) for s in SPECS)
    for spec in sorted(SPECS, key=lambda s: -s.get("height_m", 1)):
        root = robot.build(spec)
        bpy.context.view_layer.update()
        lo, hi = robot.bounds(root)
        root.location.x += x - lo.x          # left edge of this robot at x
        x += (hi.x - lo.x) + tallest * 0.15
        roots.append(root)
    bpy.context.view_layer.update()
    total = x - tallest * 0.15
    for r in roots:
        r.location.x -= total / 2
    bpy.context.view_layer.update()
    studio(sc, max(tallest, total / 3))
    lens = 50
    dist = fit_dist(tallest, total, lens, aspect=16 / 9, margin=1.08)
    camera(sc, Vector((0, 0, tallest * 0.5)), dist, tallest * 0.15, 0, lens)
    render(sc, OUT / "lineup.png", (1920, 1080))
    print("done lineup", flush=True)
