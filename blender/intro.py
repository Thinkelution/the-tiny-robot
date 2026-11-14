"""Studio ident: "Thinkelution Studio presents", starring the Tiny Robot (6 s).

  blender -b --factory-startup -P blender/intro.py -- <out_dir> <tiny.json> [--res 1920x1080] [--frames 180]
        [--samples 64] [--stills 1,60,140] [--device HIP]

Story (frames at 30 fps):
  1-24    darkness; the Tiny Robot's eyes blink on, lighting the floor around it
  24-60   it checks left, right ("check... no harm. go."), then hops twice to a little floor button
  60-72   it presses the button with its right hand
  72-120  giant THINKELUTION letters behind it power on one by one; backlights throw shafts through the haze;
          one letter flickers, the robot startles, the letter catches
  110-170 the camera racks focus and cranes up and back to reveal the block-T logo and the whole title;
          STUDIO lights; "presents" fades in
  150-165 a happy hop
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import look  # noqa: E402
import materials  # noqa: E402
import robot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
argv = sys.argv[sys.argv.index("--") + 1:]
opts, pos = {}, []
i = 0
while i < len(argv):
    if argv[i].startswith("--"):
        opts[argv[i][2:]] = argv[i + 1]
        i += 2
    else:
        pos.append(argv[i])
        i += 1
OUT, SPEC = Path(pos[0]), pos[1]
RES = tuple(int(v) for v in opts.get("res", "1920x1080").split("x"))
FRAMES = int(opts.get("frames", 180))
PORTRAIT = RES[1] > RES[0]
TITLE_FONT = ROOT / "assets/fonts/Poppins-Medium.ttf"      # clean geometric sans, SIL OFL
LIGHT_FONT = ROOT / "assets/fonts/Poppins-Light.ttf"


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
    sc.cycles.samples = int(opts.get("samples", 64))
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
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.fps = 30
    sc.frame_start, sc.frame_end = 1, FRAMES
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(OUT) + "/"
    sc.render.use_motion_blur = True
    w = bpy.data.worlds.new("void")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.008, 0.016, 1)
    sc.world = w
    return sc


def key(datablock, path, frames_values, index=-1):
    for fr, v in frames_values:
        if index >= 0:
            getattr(datablock, path)[index] = v
            datablock.keyframe_insert(path, index=index, frame=fr)
        else:
            setattr(datablock, path, v)
            datablock.keyframe_insert(path, frame=fr)


def letter_mat(name, on_frames):
    """Cream lacquer; a warm inner glow that switches on (with an optional flicker) at the given keyframes."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = materials.hex_rgb("#efe6d2")
    b.inputs["Roughness"].default_value = 0.32
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.06
    b.inputs["Emission Color"].default_value = materials.hex_rgb("#ffd9a0")
    s = b.inputs["Emission Strength"]
    for fr, v in on_frames:
        s.default_value = v
        s.keyframe_insert("default_value", frame=fr)
    return m


def make_letter(sc, ch, size, x, y, z, mat, extrude, font=TITLE_FONT):
    cu = bpy.data.curves.new(ch, "FONT")
    cu.body = ch
    cu.font = bpy.data.fonts.load(str(font), check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = extrude * 0.18
    cu.bevel_resolution = 4
    cu.align_x = "LEFT"
    ob = bpy.data.objects.new(ch, cu)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(90), 0, 0)
    ob.location = (x, y, z)
    cu.materials.append(mat)
    bpy.context.view_layer.update()
    return ob


def word(sc, text, size, y, z, start, step, extrude, flicker_at=None, font=TITLE_FONT, track=0.18):
    """Lay out a word letter by letter (so each can light on its own), centred on x = 0."""
    obs, x = [], 0.0
    for k, ch in enumerate(text):
        t0 = start + k * step
        on = [(1, 0.0), (t0, 0.0), (t0 + 4, 1.3), (t0 + 10, 0.8)]
        if flicker_at is not None and k == flicker_at:
            on = [(1, 0.0), (t0, 0.0), (t0 + 3, 2.0), (t0 + 6, 0.0), (t0 + 9, 1.6), (t0 + 11, 0.0),
                  (t0 + 22, 0.0), (t0 + 25, 2.4), (t0 + 32, 1.4)]
        ob = make_letter(sc, ch, size, x, y, z, letter_mat(f"letter_{text}_{k}", on), extrude, font)
        x += ob.dimensions.x + size * track
        obs.append(ob)
    width = x - size * track
    for ob in obs:
        ob.location.x -= width / 2
    return obs, width


def block(sc, size, loc, mat, bevel=0.02):
    ob = robot.mesh_box("blk", size, "box", sc.collection, mat, bevel, 3)
    ob.location = loc
    return ob


def logo(sc, at, s, on_frame):
    top = bpy.data.materials.new("logo_top")
    top.use_nodes = True
    nt = top.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = materials.hex_rgb("#7a3cf0")
    ramp.color_ramp.elements[1].color = materials.hex_rgb("#3a6cf6")
    nt.links.new(sep.outputs["X"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Coat Weight"].default_value = 1.0
    em = bsdf.inputs["Emission Strength"]
    for fr, v in ((1, 0.0), (on_frame, 0.0), (on_frame + 8, 2.5), (on_frame + 20, 1.2)):
        em.default_value = v
        em.keyframe_insert("default_value", frame=fr)
    black = materials.make({"id": "logo_black", "kind": "plastic", "color": "#2a2d36", "roughness": 0.2,
                            "wear": 0.0, "dirt": 0.0, "textured": False})
    parts = [((1.0, 0.36, 0.14), (0.0, 0.0, 0.93), top), ((0.34, 0.36, 0.34), (-0.33, 0.0, 0.69), black),
             ((0.34, 0.36, 0.6), (0.0, 0.0, 0.48), black)]
    return [block(sc, tuple(v * s for v in size), Vector(at) + Vector(loc) * s, m, 0.012 * s) for size, loc, m in parts]


def spot(sc, name, loc, target, energy, color, size_deg=30, soft=0.2, scatter=True):
    ld = bpy.data.lights.new(name, "SPOT")
    ld.energy = energy
    ld.color = color
    ld.spot_size = math.radians(size_deg)
    ld.spot_blend = 0.5
    ld.shadow_soft_size = soft
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    ob.visible_volume_scatter = scatter
    return ob


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sc = setup()
    spec = json.loads(Path(SPEC).read_text(encoding="utf-8"))
    tiny = robot.build(spec)
    bpy.context.view_layer.update()
    lo, hi = robot.bounds(tiny)
    h = hi.z - lo.z

    floor = materials.make({"id": "ident_floor", "kind": "plastic", "color": "#1a1d24", "roughness": 0.28,
                            "wear": 0.0, "dirt": 0.0, "tex_tile": 0.8})
    block(sc, (240, 240, 0.02), (0, 20, -0.01), floor, 0)

    # giant letters standing on a plinth behind the robot; STUDIO and "presents" on the plinth's front face
    LY, LS = 2.6, 1.25 if not PORTRAIT else 0.9
    PH = LS * 0.72                                               # plinth height
    letters, width = word(sc, "THINKELUTION", LS, LY, PH, 78, 3, 0.16, flicker_at=7)
    plinth_m = materials.make({"id": "plinth", "kind": "plastic", "color": "#202430", "roughness": 0.3,
                               "wear": 0.0, "dirt": 0.0, "textured": False})
    pw = width + LS * 1.2
    block(sc, (pw, 1.0, PH), (0.0, LY - 0.25, PH / 2), plinth_m, 0.04)
    studio, sw = word(sc, "STUDIO", LS * 0.3, LY - 0.77, PH * 0.42, 128, 3, 0.03, font=LIGHT_FONT, track=0.6)
    pres = make_letter(sc, "presents", LS * 0.17, 0, LY - 0.77, PH * 0.12,
                       letter_mat("presents", [(1, 0.0), (148, 0.0), (160, 1.2)]), 0.01, LIGHT_FONT)
    pres.data.align_x = "CENTER"
    pres.location.x = 0
    # unlit text stays out of frame until it lights
    for ob, fr in [(o, 126) for o in studio] + [(pres, 146)]:
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=1)
        ob.keyframe_insert("hide_render", frame=fr - 1)
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=fr)
    # a little floor button for the robot to press
    btn_base = materials.make({"id": "btn_base", "kind": "bare_metal", "color": "#6d6f75", "roughness": 0.35,
                               "wear": 0.2, "dirt": 0.2, "tex_tile": 0.3})
    BX, BY = -0.42, -0.05                # on the robot's right, the side facing the opening camera
    block(sc, (0.14, 0.14, 0.07), (BX, BY, 0.035), btn_base, 0.01)
    cap = bpy.data.materials.new("btn_cap")
    cap.use_nodes = True
    cb = cap.node_tree.nodes["Principled BSDF"]
    cb.inputs["Base Color"].default_value = materials.hex_rgb("#ff5a3a")
    cb.inputs["Emission Color"].default_value = materials.hex_rgb("#ff5a3a")
    key(cb.inputs["Emission Strength"], "default_value", [(1, 0.6), (66, 0.6), (70, 6.0), (90, 1.5)])
    btn = block(sc, (0.09, 0.09, 0.03), (BX, BY, 0.085), cap, 0.01)
    key(btn, "location", [(1, 0.085), (64, 0.085), (67, 0.07), (74, 0.085)], index=2)

    # atmosphere + grade
    look.atmosphere(sc, density=0.016, color=(0.75, 0.8, 0.9), anisotropy=0.65, centre=(0, 4, 0), size=(30, 30, 10))
    look.grade(sc, bloom=0.55, vignette=0.42)

    # lights: eye glow (floor/letters only), back-lights behind the letters (shafts), key on the robot, rim
    lit = bpy.data.collections.new("eyeglow_receivers")
    sc.collection.children.link(lit)
    for ob in list(sc.collection.objects):
        if ob.type in ("MESH", "FONT") and not ob.name.startswith(spec["id"]):
            lit.objects.link(ob)
    eg = bpy.data.lights.new("eyeglow", "POINT")
    eg.color = (0.55, 1.0, 0.7)
    eg.shadow_soft_size = 0.04
    eg.shadow_soft_size = 0.12
    key(eg, "energy", [(1, 0.0), (14, 0.0), (24, 1.0)])
    ego = bpy.data.objects.new("eyeglow", eg)
    sc.collection.objects.link(ego)
    ego.location = (0, -0.2, h * 0.6)
    ego.light_linking.receiver_collection = lit
    for k, x in enumerate((-width * 0.38, 0.0, width * 0.38)):
        sp = spot(sc, f"back{k}", (x, LY + 3.0, 4.8), (x * 0.6, -3.0, 0.0), 0.0, (1.0, 0.86, 0.66), 34, 0.3)
        key(sp.data, "energy", [(1, 0.0), (84 + k * 8, 0.0), (100 + k * 8, 1100.0)])
    kl = spot(sc, "key", (-1.2, -1.6, 1.6), (0, 0, h * 0.5), 0.0, (1.0, 0.93, 0.82), 28, 0.25, scatter=False)
    key(kl.data, "energy", [(1, 0.0), (20, 0.0), (40, 45.0)])
    fill = bpy.data.lights.new("title_fill", "AREA")
    fill.size = 6.0
    fill.color = (0.85, 0.9, 1.0)
    key(fill, "energy", [(1, 0.0), (110, 0.0), (140, 900.0)])
    fo = bpy.data.objects.new("title_fill", fill)
    sc.collection.objects.link(fo)
    fo.location = (0.0, LY - 9.0, PH + 3.0)
    fo.rotation_euler = (Vector((0.0, LY, PH + LS * 0.4)) - fo.location).to_track_quat("-Z", "Y").to_euler()
    fo.visible_volume_scatter = False
    rim = spot(sc, "rim", (0.9, 1.2, 0.9), (0, 0, h * 0.5), 0.0, (0.55, 0.72, 1.0), 30, 0.2, scatter=False)
    key(rim.data, "energy", [(1, 0.0), (80, 0.0), (100, 60.0)])

    # --- the robot's performance
    eyes = [o for o in tiny.children_recursive if o.get("role") == "eye"]
    eyes_root = next(o for o in tiny.children_recursive if o.get("role") == "eyes")
    head = next(o for o in tiny.children_recursive if o.get("role") == "head" and o.type == "EMPTY")
    # the button is on the robot's right (-X, the camera side), so it presses with its right hand
    hand = next(o for o in tiny.children_recursive if o.get("role") == "hand_r" and o.type == "EMPTY")
    feet = [o for o in tiny.children_recursive if o.get("role") in ("foot_l", "foot_r") and o.type == "EMPTY"]

    def face(fr, **vals):
        for e in eyes:
            for kb in e.data.shape_keys.key_blocks[1:]:
                kb.value = vals.get(kb.name, 0.0)
                kb.keyframe_insert("value", frame=fr)

    eye_mat = next(m for m in bpy.data.materials if m.name.endswith("_eye"))
    em = next(n for n in eye_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Emission Strength"]
    base_em = em.default_value
    key(em, "default_value", [(1, 0.0), (12, 0.0), (16, base_em * 1.6), (22, base_em)])
    face(1, blink=1.0)
    face(14, blink=1.0)
    face(20)
    # check left, right
    sw = spec["face"]["screen"][0] * 0.16
    x0 = eyes_root.location.x
    key(eyes_root, "location", [(26, x0), (31, x0 - sw), (38, x0 - sw), (43, x0 + sw), (50, x0 + sw), (54, x0)],
        index=0)
    key(head, "rotation_euler", [(26, 0.0), (31, math.radians(10)), (38, math.radians(10)), (43, math.radians(-10)),
                                 (50, math.radians(-10)), (54, 0.0)], index=2)
    face(55, blink=1.0)
    face(58)
    # two hops toward the button (button sits to the front-right)
    tx, ty = BX + 0.3, BY + 0.06
    root_keys = [(56, (0, 0, 0)), (60, (tx * 0.5, ty * 0.5, 0.06)), (63, (tx * 0.5, ty * 0.5, 0.0)),
                 (66, (tx, ty, 0.05)), (69, (tx, ty, 0.0))]
    for fr, p in root_keys:
        tiny.location = p
        tiny.keyframe_insert("location", frame=fr)
    for ft in feet:
        key(ft, "rotation_euler", [(56, 0.0), (58, math.radians(-14)), (61, 0.0), (64, math.radians(-14)), (67, 0.0)],
            index=0)
    # press with the right hand: a slight turn, the hand reaches out sideways and down onto the cap, in full view
    key(tiny, "rotation_euler", [(66, 0.0), (70, math.radians(-8)), (84, math.radians(-8)), (96, 0.0)], index=2)
    hx, hy, hz = hand.location.x, hand.location.y, hand.location.z
    key(hand, "location", [(66, hx), (70, hx - 0.07), (73, hx - 0.1), (78, hx - 0.1), (84, hx)], index=0)
    key(hand, "location", [(66, hy), (70, hy - 0.03), (73, hy - 0.05), (78, hy - 0.05), (84, hy)], index=1)
    key(hand, "location", [(66, hz), (70, hz + 0.02), (73, hz - 0.045), (76, hz - 0.03), (84, hz)], index=2)
    # watch the letters light, startle at the flicker, look up in awe
    face(80, wide=1.0)
    face(104, wide=1.0)
    face(106, blink=1.0)       # the flicker: a startled blink
    face(109, wide=1.0)
    key(eyes_root, "location", [(80, eyes_root.location.z), (90, eyes_root.location.z + 0.02), (140, eyes_root.location.z + 0.02),
                                (150, eyes_root.location.z)], index=2)
    key(head, "rotation_euler", [(80, 0.0), (92, math.radians(14)), (140, math.radians(14)), (150, 0.0)], index=0)
    face(148, wide=1.0)
    face(154, happy=1.0)
    for fr, z in ((154, 0.0), (159, 0.09), (164, 0.0), (167, 0.015), (170, 0.0)):
        tiny.location.z = z
        tiny.keyframe_insert("location", index=2, frame=fr)

    # --- camera: macro beside the robot, rack focus, crane up and back to the full title
    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit = "HORIZONTAL" if not PORTRAIT else "VERTICAL"
    cd.dof.use_dof = True
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    focus = bpy.data.objects.new("focus", None)
    sc.collection.objects.link(focus)
    cd.dof.focus_object = focus
    mid_x = (BX + tx) / 2 if False else (BX + (BX + 0.3)) / 2      # between the robot's stop and the button
    near_aim = Vector((mid_x * 0.8, -0.02, 0.15))
    near_p = Vector((mid_x * 0.8 + (0.28 if not PORTRAIT else 0.25), -1.0 if not PORTRAIT else -1.6, 0.17))
    far_dist = (pw * 0.8) / (2 * math.tan(math.radians(36) / 2)) * (1.0 if not PORTRAIT else 2.7)
    cam_z = PH + LS * (0.9 if not PORTRAIT else 3.2)        # portrait looks down more, so the robot sits below the sub-lines
    far_p, far_aim = Vector((0.0, LY - far_dist, cam_z)), Vector((0.0, LY - 0.4, PH + LS * 0.2))
    shots = [(1, near_p, near_aim, 32), (104, near_p + Vector((0.08, -0.1, 0.03)), near_aim, 32),
             (150, far_p, far_aim, 36), (FRAMES, far_p + (far_aim - far_p) * 0.04, far_aim, 36)]
    for fr, p, aim, lens in shots:
        cam.location = p
        cam.rotation_euler = (aim - p).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_euler", frame=fr)
        cd.keyframe_insert("lens", frame=fr)
    for fr, p, fstop in ((1, Vector((-0.15, 0.0, 0.15)), 2.0), (100, Vector((-0.2, 0.0, 0.15)), 2.0),
                         (118, Vector((0.0, LY, PH + LS * 0.5)), 2.2), (150, Vector((0.0, LY - 0.5, PH)), 5.6)):
        focus.location = p
        focus.keyframe_insert("location", frame=fr)
        cd.dof.aperture_fstop = fstop
        cd.dof.keyframe_insert("aperture_fstop", frame=fr)
    # ease the crane
    if cam.animation_data and cam.animation_data.action:
        try:
            for fc in cam.animation_data.action.layers[0].strips[0].channelbags[0].fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "EASE_IN_OUT"
        except Exception:
            pass
    sc.camera = cam

    if "stills" in opts:
        for fr in [int(v) for v in opts["stills"].split(",")]:
            sc.frame_set(fr)
            sc.render.filepath = str(OUT / f"still_{fr:04d}.png")
            bpy.ops.render.render(write_still=True)
        return
    if "start" in opts:                # resume a stopped shot from its first missing frame
        sc.frame_start = int(opts["start"])
    sc.frame_set(sc.frame_start)
    bpy.ops.render.render(animation=True)


main()
