"""Transparent 3/4 render of the Tiny Robot for the website hero.
  blender -b --factory-startup -P tiny_cutout.py -- <project root> <out.png>
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

root_dir, out = sys.argv[sys.argv.index("--") + 1:][:2]
sys.path.insert(0, str(Path(root_dir) / "blender"))
import robot  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "HIP"
prefs.refresh_devices()
for d in prefs.devices:
    d.use = d.type != "CPU"
sc.cycles.device = "GPU"
sc.cycles.samples = 96
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Punchy"
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
world = bpy.data.worlds.new("w")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.55, 0.6, 0.68, 1)
bg.inputs["Strength"].default_value = 0.45
sc.world = world

spec = json.load(open(Path(root_dir) / "films/the-tiny-robot/cast/tiny.json", encoding="utf-8"))
rob = robot.build(spec, sc.collection)
bpy.context.view_layer.update()
lo, hi = robot.bounds(rob)
h = hi.z - lo.z
centre = (lo + hi) / 2


def area(name, loc, energy, size_, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy * h * h * 2.2
    ld.size = size_ * h
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.visible_camera = False
    ob.location = centre + Vector(loc) * h
    ob.rotation_euler = (centre - ob.location).to_track_quat("-Z", "Y").to_euler()


area("key", (-2.2, -2.6, 2.2), 300, 1.6, (1.0, 0.95, 0.88))
area("fill", (2.8, -1.8, 0.8), 90, 2.4, (0.85, 0.92, 1.0))
area("rim", (1.6, 2.6, 2.0), 380, 1.0, (0.75, 1.0, 0.85))

cd = bpy.data.cameras.new("cam")
cd.lens = 85
cam = bpy.data.objects.new("cam", cd)
sc.collection.objects.link(cam)
a = math.radians(-24)
w = max(hi.x - lo.x, hi.y - lo.y)
fov = 2 * math.atan(36 / 2 / cd.lens)
dist = max(w, h) * 1.22 / 2 / math.tan(fov / 2) + w / 2
cam.location = centre + Vector((math.sin(a) * dist, -math.cos(a) * dist, h * 0.35))
cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
sc.render.resolution_x = sc.render.resolution_y = 800
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
