"""Animated shots (runs inside Blender): a set and its robots from setshot, then the performance from anim.py.

  blender -b --factory-startup -P blender/animshot.py -- <out_dir> <shot> [--samples N] [--res WxH] [--preview]
            [--stills 1,60,120] [--start F] [--device HIP|OPTIX]

Writes <out_dir>/<shot>/####.png. --stills renders only those frames, for a quick check before a full render.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anim  # noqa: E402
import robot  # noqa: E402
import setshot  # noqa: E402

opts, args = setshot.opts, setshot.args
OUT = Path(args[0]).resolve()


def s02_grove_entry(sc, cam, roots):
    """S02, beats 2-4: Tiny trots in from the street, stops exactly where the pavement meets the grass, checks
    (antenna amber, eyes left, right), "Check... no harm. Go.", antenna green, steps onto the grass and walks round a
    fallen slab leaf instead of over it. Through the north gate, so the morning sun is behind the camera."""
    tiny = anim.Actor(next(r for r, spec in roots if spec["id"] == "tiny"))
    f = tiny.walk([(0.0, 33.6), (0.0, 32.55)], start=10, speed=0.5)
    f = tiny.check(f + 6)
    f = tiny.walk([(0.0, 32.55), (0.0, 31.6), (0.45, 30.9), (0.45, 30.2), (0.0, 29.6)], start=f + 4, speed=0.5)
    tiny.idle(1, sc.frame_end)
    # the camera: low at Tiny's height inside the gate, drifting back a little as Tiny comes on
    cam.keyframe_insert("location", frame=1)
    cam.location += Vector((0.1, -1.1, 0.02))
    cam.keyframe_insert("location", frame=sc.frame_end)
    return f


def s02_full(sc, cam, roots):
    import s02
    return s02.build(sc, roots)


ANIM = {
    "s02_full": dict(
        frames=1900, action=s02_full,
        stage=dict(set="grove", tod="morning", water=0.85, haze=0.0012,
                   clear=[(1.2, 26.6, 2.5), (0.0, 30.0, 2.5), (3.3, 15.6, 2.0), (0.6, 13.0, 1.5), (2.9, 15.0, 1.5),
                          (2.2, 0.9, 1.0), (-0.6, -6.6, 2.5), (1.2, -4.6, 1.5), (-0.4, -6.2, 2.0), (5.8, -5.5, 1.5),
                          (2.3, -3.4, 1.0), (-0.6, -3.4, 1.0), (-1.8, -4.6, 1.5), (-2.6, -3.4, 1.5),
                          (-15.0, -15.5, 3.0), (-13.2, -13.4, 3.0), (1.6, 7.5, 2.5), (8.0, 7.5, 2.5)],
                   cam=((0.85, 28.2, 0.3), (-0.1, 33.0, 0.42), 34, None),
                   robots=[("tiny", 0.0, 33.6, 0), ("mossback", 9.4, 3.4, 0), ("primly", 30.0, -30.0, 0)])),
    "s02_grove_entry": dict(
        frames=264, action=s02_grove_entry, leaf=(0.0, 30.55), apron=(0.0, 33.6),
        stage=dict(set="grove", tod="morning", water=0.85, haze=0.0012, clear=[(0.9, 28.0, 2.5), (0.0, 30.5, 2.5)],
                   cam=((0.85, 28.2, 0.3), (-0.1, 33.0, 0.42), 34, 2.8),
                   robots=[("tiny", 0.0, 33.6, 0)])),
}


def leaf(sc, x, y, apron):
    """The fallen slab leaf Tiny walks round (S02), and the paved apron outside the south gate: the grey street
    Tiny trots in from, level with the grass, so "where the pavement meets the grass" is one clean line."""
    import world
    m = world.mat("s02_leaf", "plastic", "#8a7038", wear=0.0, dirt=0.2, tile=1.0)
    ob = world.box(sc.collection, "s02_leaf", (0.26, 0.18, 0.018), (x, y, 0.012), m, 0.004, rot=0.5)
    pave = world.tex_mat("gate_apron", "concrete", "#9a958a", tile=1.5, rough=0.85)
    world.box(sc.collection, "gate_apron", (3.4, 3.2, 0.2), (apron[0], apron[1], -0.1), pave, 0.02)
    return ob


def press(sc, roots):
    """Grass gives under every walking robot's feet, in the grass patches its path crosses."""
    import plants
    grass = [o for o in bpy.data.objects if o.name.startswith("grass_") and o.type == "MESH"]
    if not grass:
        return
    for (r, spec) in roots:
        if spec.get("locomotion", "walk") not in ("walk", "hop"):
            continue
        feet = [o for o in r.children_recursive if o.type == "MESH" and ":foot_" in o.name]
        # only the patches near where this robot goes during the shot
        xs, ys = [], []
        for f in range(sc.frame_start, sc.frame_end + 1, 3):
            sc.frame_set(f)
            xs.append(r.matrix_world.translation.x)
            ys.append(r.matrix_world.translation.y)
        # a dense meadow along the path, so the feet have grass to give (the Grove's own grass is sparse);
        # kept off hard ground (the gate apron) and the props named in the shot
        ctrl = bpy.data.objects.get("grove_water")
        if ctrl is not None:
            import random
            rnd = random.Random(7)
            keep = [tuple(k) for k in sc.get("keep_clear", [])]
            pts = []
            path = list(zip(xs, ys))
            x0, x1, y0, y1 = min(xs) - 1.6, max(xs) + 1.6, min(ys) - 1.6, max(ys) + 1.6
            n = int((x1 - x0) * (y1 - y0) * 7)
            for _ in range(n):
                px, py = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                if abs(py) > 31.9 or any(abs(px - kx) < kr and abs(py - ky) < kr for (kx, ky, kr) in keep):
                    continue
                if min((px - a) ** 2 + (py - b) ** 2 for (a, b) in path) > 1.5 ** 2:
                    continue                                   # only near where the robot actually walks
                pts.append((px, py, rnd.uniform(0.45, 0.75)))       # lawn height: blades under Tiny's eyes
            grass += plants.grass(sc.collection, rnd, ctrl, pts, blades=7, name="grass_meadow", chunk=2.5)
        near = []
        for g in grass:
            lo = [min(v.co[i] for v in g.data.vertices) for i in (0, 1)]
            hi = [max(v.co[i] for v in g.data.vertices) for i in (0, 1)]
            if lo[0] - 1 < max(xs) and hi[0] + 1 > min(xs) and lo[1] - 1 < max(ys) and hi[1] + 1 > min(ys):
                near.append(g)
        if "nopress" not in opts:
            plants.press_grass(near, feet, radius=spec.get("height_m", 1.0) * 0.85)
        print(f"press: {len(near)} grass patches give under {spec['id']}'s {len(feet)} feet", flush=True)
    sc.frame_set(sc.frame_start)


def main():
    name = args[1]
    shot = ANIM[name]
    sc, cam, roots = setshot.stage(shot["stage"])
    sc.frame_start, sc.frame_end = 1, shot["frames"]
    sc.render.fps = anim.FPS
    if "leaf" in shot:
        leaf(sc, *shot["leaf"], shot["apron"])
        sc["keep_clear"] = [(shot["leaf"][0], shot["leaf"][1], 0.22)]
    end = shot["action"](sc, cam, roots)
    if isinstance(end, int):
        sc.frame_end = end
    press(sc, roots)
    # keep focus on the first robot as it moves
    if cam.data.dof.use_dof:
        cam.data.dof.focus_object = roots[0][0]
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.4
    sc.render.use_persistent_data = True
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    if "stills" in opts:
        for f in [int(v) for v in opts["stills"].split(",")]:
            sc.frame_set(f)
            sc.render.filepath = str(out / f"still_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
        print("stills ->", out, flush=True)
        return
    if "start" in opts:
        sc.frame_start = int(opts["start"])
    sc.render.filepath = str(out) + "/"
    bpy.ops.render.render(animation=True)
    print("rendered", name, "->", out, flush=True)


main()
