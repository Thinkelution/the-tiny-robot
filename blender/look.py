"""The film's look: atmosphere, character rim light (light-linked), and a compositor grade (Blender 5.3).

  import look; look.atmosphere(sc); look.rim(sc, robot_root, h); look.grade(sc)

- atmosphere: a thin volumetric haze in the world, so lamps, windows and the sun throw shafts and the city gets depth
- rim: two lights that only light the character (light linking), a cool back rim and a warm kicker, so the robot
  separates from the background the way a lit character does in a feature film
- grade: bloom on bright lights and eyes, slight lens distortion and dispersion, warm highlights / cool shadows,
  a soft vignette. Built as a compositor node group (5.x has no Composite node: the group output is the image).
"""
import math

import bpy
from mathutils import Vector


def atmosphere(sc, density=0.012, anisotropy=0.55, color=(0.62, 0.7, 0.85), centre=(0, 30, 40),
               size=(260, 260, 90)):
    """Haze in a big closed box over the city, not in the world: a world volume reaches to infinity, so sunlight
    crossing it is fully absorbed and the sun stops lighting anything."""
    m = bpy.data.materials.new("haze")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = anisotropy
    vol.inputs["Color"].default_value = (*color, 1)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    me = bpy.data.meshes.new("haze")
    sx, sy, sz = (v / 2 for v in size)
    vs = [(-sx, -sy, -1), (sx, -sy, -1), (sx, sy, -1), (-sx, sy, -1), (-sx, -sy, sz * 2), (sx, -sy, sz * 2),
          (sx, sy, sz * 2), (-sx, sy, sz * 2)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(vs, [], fs)
    me.materials.append(m)
    ob = bpy.data.objects.new("haze", me)
    sc.collection.objects.link(ob)
    ob.location = (centre[0], centre[1], 0)
    sc.cycles.volume_bounces = 1
    sc.cycles.volume_step_rate = 8.0          # smooth haze: coarse steps look the same and cost far less
    sc.cycles.volume_max_steps = 96


def _light(sc, name, kind, loc, target, energy, size, color):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    else:
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    ob.visible_volume_scatter = False
    return ob


def rim(sc, root, h, strength=1.0):
    """Cool back rim + warm side kicker that light only this robot."""
    coll = bpy.data.collections.new(f"rimlink_{root.name}")
    sc.collection.children.link(coll)
    for ob in [root] + list(root.children_recursive):
        if ob.type == "MESH":
            coll.objects.link(ob)
    c = root.matrix_world.translation + Vector((0, 0, h * 0.55))
    a = _light(sc, "rim_cool", "AREA", c + Vector((h * 1.4, h * 2.2, h * 1.6)), c, 420 * h * h * strength,
               h * 0.6, (0.55, 0.75, 1.0))
    b = _light(sc, "rim_warm", "AREA", c + Vector((-h * 2.0, h * 0.6, h * 0.9)), c, 260 * h * h * strength,
               h * 0.5, (1.0, 0.7, 0.4))
    for lt in (a, b):
        lt.light_linking.receiver_collection = coll
    return a, b


def _set(node, name, value):
    for s in node.inputs:
        if s.name == name and s.enabled:
            s.default_value = value
            return
    raise KeyError(f"{node.bl_idname}: no input {name}")


def grade(sc, bloom=0.35, vignette=0.32, warm=0.06):
    ng = bpy.data.node_groups.new("film_grade", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    n = ng.nodes
    rl = n.new("CompositorNodeRLayers")
    out = n.new("NodeGroupOutput")
    glare = n.new("CompositorNodeGlare")
    _set(glare, "Type", "Bloom")
    _set(glare, "Quality", "High")
    _set(glare, "Threshold", 0.9)
    _set(glare, "Strength", bloom)
    _set(glare, "Saturation", 1.1)
    ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
    lens = n.new("CompositorNodeLensdist")
    _set(lens, "Distortion", -0.008)
    _set(lens, "Dispersion", 0.012)
    ng.links.new(glare.outputs["Image"], lens.inputs["Image"])
    cb = n.new("CompositorNodeColorBalance")
    lift = [s for s in cb.inputs if s.name == "Lift" and s.enabled]
    gain = [s for s in cb.inputs if s.name == "Gain" and s.enabled]
    if lift and hasattr(lift[-1].default_value, "__len__"):
        lift[-1].default_value = (0.97, 0.99, 1.04, 1)          # cool shadows
    if gain and hasattr(gain[-1].default_value, "__len__"):
        gain[-1].default_value = (1.0 + warm, 1.0, 1.0 - warm, 1)  # warm highlights
    ng.links.new(lens.outputs["Image"], cb.inputs["Image"])
    # vignette: soft ellipse mask multiplied in
    mask = n.new("CompositorNodeEllipseMask")
    _set(mask, "Size", (0.92, 0.82))
    blur = n.new("CompositorNodeBlur")
    for s in blur.inputs:
        if s.name == "Size" and s.enabled:
            s.default_value = (300, 300) if hasattr(s.default_value, "__len__") else 300
    ng.links.new(mask.outputs["Mask"], blur.inputs["Image"])
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    fac = next(s for s in mix.inputs if s.name == "Factor" and s.enabled)
    fac.default_value = vignette
    a = next(s for s in mix.inputs if s.name == "A" and s.enabled)
    b = next(s for s in mix.inputs if s.name == "B" and s.enabled)
    ng.links.new(cb.outputs["Image"], a)
    ng.links.new(blur.outputs["Image"], b)
    ng.links.new(mix.outputs[next(i for i, s in enumerate(mix.outputs) if s.enabled)], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return ng
