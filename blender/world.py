"""Gridhaven, simple and boxy: a paved square ringed by block towers at blue hour (runs inside Blender).

  import world; world.build(scene, seed=7)

Everything is boxes and cylinders. Studio finish comes from the texture library (textures/lib) through texmat,
shader-driven window grids (lit at random, warm), a dusk sky, lamp pools, and distance haze baked into every world
material (Camera Data > view distance), which reads like atmospheric depth without volumetric cost.
Robots perform near the origin; cameras look toward +Y.
"""
import math
import random

import bpy
from mathutils import Vector

import facade
import materials
import robot
import texmat

HAZE = (0.10, 0.14, 0.24)        # distance-haze colour, linear; set per time of day by build()
TOD = {
    # sky gradient (horizon, middle, zenith), sky strength, sun (energy, colour, elevation deg, heading deg),
    # haze, windows (lit fraction, strength), lamp energy (0 = off), wet ground
    "dusk": dict(sky=((0.95, 0.52, 0.28), (0.35, 0.33, 0.5), (0.03, 0.06, 0.16)), sky_strength=0.45,
                 sun=(1.2, (1.0, 0.62, 0.38), 8, 200), haze=(0.10, 0.14, 0.24), windows=(0.4, 0.55), lamps=900,
                 wet=False),
    "night_rain": dict(sky=((0.10, 0.075, 0.07), (0.025, 0.03, 0.055), (0.004, 0.006, 0.014)), sky_strength=0.7,
                       sun=(0.12, (0.6, 0.72, 1.0), 55, 140), haze=(0.035, 0.045, 0.075), windows=(0.5, 0.8),
                       lamps=1500, wet=True),
    "morning": dict(sky=((1.0, 0.9, 0.76), (0.42, 0.63, 0.95), (0.12, 0.3, 0.78)), sky_strength=1.15,
                    sun=(9.0, (1.0, 0.84, 0.62), 24, -32), haze=(0.78, 0.84, 0.95), windows=(0.0, 0.0), lamps=0,
                    wet=False, rig=0.25, haze_amount=0.35, sun_angle=0.8),
    "sunrise": dict(sky=((1.0, 0.55, 0.32), (0.55, 0.5, 0.62), (0.12, 0.2, 0.45)), sky_strength=0.9,
                    sun=(6.0, (1.0, 0.6, 0.32), 6, 90), haze=(0.95, 0.7, 0.55), windows=(0.2, 0.6), lamps=0,
                    wet=False, rig=0.25, haze_amount=0.4, sun_angle=1.0),
    "golden_morning": dict(sky=((1.0, 0.82, 0.6), (0.5, 0.66, 0.92), (0.15, 0.32, 0.75)), sky_strength=1.1,
                           sun=(9.0, (1.0, 0.78, 0.5), 26, 72), haze=(0.95, 0.85, 0.72), windows=(0.0, 0.0),
                           lamps=0, wet=False, rig=0.25, haze_amount=0.35, sun_angle=0.8),
    "night": dict(sky=((0.16, 0.1, 0.08), (0.03, 0.045, 0.1), (0.005, 0.01, 0.03)), sky_strength=1.1,
                  sun=(0.35, (0.6, 0.72, 1.0), 55, 140), haze=(0.035, 0.045, 0.075), windows=(0.62, 1.4),
                  lamps=1500, wet=False, sheen=True),
}
CFG = TOD["dusk"]
SKY_ZENITH = (0.03, 0.06, 0.16)
SKY_HORIZON = (0.95, 0.52, 0.28)
WINDOW_WARM = (1.0, 0.42, 0.1)
PALETTE = ["#8a9aa6", "#b98e5d", "#9c5a48", "#5f7f86", "#c9b48a", "#6d6f86", "#a7a199", "#7b8f6a"]


# ------------------------------------------------------------------ materials
def _haze(mat, start=22.0, end=140.0, amount=None):
    """Blend the material toward the haze colour with distance from the camera."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    surf = out.inputs["Surface"].links[0].from_socket
    cam = nt.nodes.new("ShaderNodeCameraData")
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.interpolation_type = "SMOOTHSTEP"
    nt.links.new(cam.outputs["View Distance"], rng.inputs["Value"])
    rng.inputs["From Min"].default_value = start
    rng.inputs["From Max"].default_value = end
    rng.inputs["To Max"].default_value = CFG.get("haze_amount", 0.85) if amount is None else amount
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = HAZE + (1,)
    em.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(rng.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(surf, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def mat(mid, kind, color, wear=0.3, dirt=0.5, rough=0.6, tile=2.0, haze=True, **extra):
    name = f"w_{mid}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = materials.make({"id": name, "kind": kind, "color": color, "wear": wear, "dirt": dirt, "roughness": rough,
                        "tex_tile": tile, **extra})
    return _haze(m) if haze else m


def tex_mat(mid, tid, tint=None, tile=2.0, rough=0.8, bump=0.6, wet=False):
    """A material straight from one library texture (concrete, asphalt, bark, leaves...)."""
    name = f"w_{mid}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    co = texmat._uv(g, tile)
    col = texmat._img(g, tid, "color", co).outputs["Color"]
    if tid in ("concrete",) or tint:
        det = texmat._detail(g, col, tid, 3.0)
        base = texmat._mul(g, materials.hex_rgb(tint or "#9a9a96"), det)
    else:
        # colour photo read raw (see texmat._img): convert to linear for the base colour
        gam = g.node("ShaderNodeGamma", Color=col, Gamma=2.2)
        base = gam.outputs[0]
        if tint:
            base = g.mix(0.5, base, materials.hex_rgb(tint))
    g.set(bsdf.inputs["Base Color"], base)
    lum = texmat._lum(g, col)
    r = g.math("ADD", rough - 0.15, g.math("MULTIPLY", lum, 0.3))
    strength = bump
    if wet and CFG.get("sheen"):
        r = g.math("MULTIPLY", r, 0.7)
    if wet and CFG["wet"]:
        # rain: everything darker and glossier, with mirror-like puddles that pick up lamps and windows
        wc = g.node("ShaderNodeTexCoord").outputs["Object"]
        pn = g.node("ShaderNodeTexNoise", Vector=wc, Scale=0.22, Detail=4.0, Roughness=0.6).outputs["Fac"]
        puddle = g.ramp(pn, 0.5, 0.56)
        base = texmat._mul(g, base, g.math("SUBTRACT", 0.62, g.math("MULTIPLY", puddle, 0.22)))
        g.set(bsdf.inputs["Base Color"], base)
        r = g.mixf(puddle, g.math("MULTIPLY", r, 0.45), 0.02)
        strength = bump * 0.5
        rip = ripples(g, g.node("ShaderNodeMapping", Vector=wc, Scale=(1.0, 1.0, 1.0)).outputs[0], puddle)
        rip_bump = g.node("ShaderNodeBump", Strength=0.6, Distance=0.004, Height=rip)
    g.set(bsdf.inputs["Roughness"], r)
    import os
    if os.path.exists(texmat.LIB / tid / "normal.png"):
        nm = g.node("ShaderNodeNormalMap", Color=texmat._img(g, tid, "normal", co, True).outputs["Color"],
                    Strength=strength)
        if wet and CFG["wet"]:
            g.set(rip_bump.inputs["Normal"], nm.outputs[0])
            g.set(bsdf.inputs["Normal"], rip_bump.outputs[0])
        else:
            g.set(bsdf.inputs["Normal"], nm.outputs[0])
    return _haze(m)


def tower_mat(mid, color, kind="concrete"):
    """Tower facade: concrete or corrugated texture in a colour, plus a window grid lit at random."""
    name = f"w_tower_{mid}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    co = texmat._uv(g, 3.0)
    col = texmat._img(g, kind, "color", co).outputs["Color"]
    det = texmat._detail(g, col, kind, 3.5)
    base = texmat._mul(g, materials.hex_rgb(color), det)
    grime = texmat._img(g, "grime", "color", texmat._uv(g, 9.0, (2.1, 4.3))).outputs["Color"]
    base = texmat._grime(g, base, grime, 0.55)
    # window grid from object coordinates: pick the in-face axis by the face normal
    tc = g.node("ShaderNodeTexCoord")
    geo = g.node("ShaderNodeNewGeometry")
    sep_p = g.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"])
    sep_n = g.node("ShaderNodeSeparateXYZ", Vector=geo.outputs["Normal"])
    facing_y = g.math("GREATER_THAN", g.math("ABSOLUTE", sep_n.outputs["Y"]), 0.5)
    u = g.mixf(facing_y, sep_p.outputs["Y"], sep_p.outputs["X"])
    v = sep_p.outputs["Z"]
    vertical = g.math("LESS_THAN", g.math("ABSOLUTE", sep_n.outputs["Z"]), 0.3)
    su, sv = 2.4, 3.2                                    # window bay width, storey height (m)
    fu = g.math("FRACT", g.math("DIVIDE", u, su))
    fv = g.math("FRACT", g.math("DIVIDE", v, sv))
    inside_u = g.math("MULTIPLY", g.math("GREATER_THAN", fu, 0.26), g.math("LESS_THAN", fu, 0.74))
    inside_v = g.math("MULTIPLY", g.math("GREATER_THAN", fv, 0.36), g.math("LESS_THAN", fv, 0.78))
    win = g.math("MULTIPLY", g.math("MULTIPLY", inside_u, inside_v), vertical)
    above = g.math("GREATER_THAN", v, 1.5)               # no windows at street level
    win = g.math("MULTIPLY", win, above)
    cell = g.node("ShaderNodeCombineXYZ", X=g.math("FLOOR", g.math("DIVIDE", u, su)),
                  Y=g.math("FLOOR", g.math("DIVIDE", v, sv)),
                  Z=g.node("ShaderNodeObjectInfo").outputs["Random"])
    rnd = g.node("ShaderNodeTexWhiteNoise", _noise_dimensions="3D", Vector=cell.outputs[0]).outputs["Value"]
    lit = g.math("MULTIPLY", g.math("GREATER_THAN", rnd, 1.0 - CFG["windows"][0]), win)
    glass = (0.015, 0.02, 0.03, 1)
    g.set(bsdf.inputs["Base Color"], g.mix(win, base, glass))
    g.set(bsdf.inputs["Roughness"], g.mixf(win, 0.85, 0.08))
    warm = g.node("ShaderNodeMix", _data_type="RGBA")
    g.set(warm.inputs["Factor"], rnd)
    warm.inputs["A"].default_value = WINDOW_WARM + (1,)
    warm.inputs["B"].default_value = (1.0, 0.6, 0.25, 1)
    g.set(bsdf.inputs["Emission Color"], warm.outputs["Result"])
    g.set(bsdf.inputs["Emission Strength"], g.math("MULTIPLY", lit, CFG["windows"][1]))
    nm = g.node("ShaderNodeNormalMap", Color=texmat._img(g, kind, "normal", co, True).outputs["Color"], Strength=0.6)
    g.set(bsdf.inputs["Normal"], nm.outputs[0])
    return _haze(m)


def emissive(mid, color, strength):
    return materials.make({"id": f"w_{mid}", "kind": "emissive", "color": color, "emission": strength})


# ------------------------------------------------------------------ pieces
_BOXES = [0]


def box(coll, name, size, loc, m, bevel=0.03, rot=0.0, shape="box"):
    _BOXES[0] += 1          # unique names: Blender's duplicate-name search gets slow with thousands of objects
    ob = robot.mesh_box(f"{name}.{_BOXES[0]:05d}", size, shape, coll, m, bevel, 2)
    ob.location = loc
    ob.rotation_euler.z = rot
    return ob


def glass_mat(mid, shop=False):
    """Window glass: reflective; lit from inside per window (face attribute "win") by time of day."""
    name = f"w_{mid}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = materials.G(m)
    bsdf = next(n for n in g.n if n.type == "BSDF_PRINCIPLED")
    attr = g.node("ShaderNodeAttribute", _attribute_type="GEOMETRY", _attribute_name="win")
    # behind each pane: a dark room, a sky-tinted reflection, or a pale curtain; a clear glossy pane on top
    look_v = g.math("FRACT", g.math("MULTIPLY", attr.outputs["Fac"], 5.13))
    behind = g.node("ShaderNodeValToRGB", Fac=look_v)
    cr = behind.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.03, 0.035, 0.045, 1)
    cr.elements[1].position, cr.elements[1].color = 0.3, (0.2, 0.27, 0.36, 1)
    curtain_el = cr.elements.new(0.68)
    curtain_el.color = (0.62, 0.56, 0.47, 1)
    pale = cr.elements.new(0.86)
    pale.color = (0.78, 0.8, 0.82, 1)
    g.set(bsdf.inputs["Base Color"], behind.outputs["Color"])
    curtain = g.math("GREATER_THAN", look_v, 0.68)
    g.set(bsdf.inputs["Metallic"], g.mixf(curtain, 0.55, 0.0))
    g.set(bsdf.inputs["Roughness"], g.mixf(curtain, 0.05, 0.6))
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.02
    frac, strength = CFG["windows"]
    if shop:
        frac, strength = min(1.0, frac * 1.6), strength * 2.2
    rv = attr.outputs["Fac"]
    lit = g.math("GREATER_THAN", rv, 1.0 - frac)
    # each lit window is a different room: warm lamps mostly, a few cool TV/blue rooms
    ramp = g.node("ShaderNodeValToRGB", Fac=g.math("FRACT", g.math("MULTIPLY", rv, 7.31)))
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (1.0, 0.42, 0.12, 1)
    cr.elements[1].position, cr.elements[1].color = 0.82, (1.0, 0.72, 0.42, 1)
    cool = cr.elements.new(0.9)
    cool.color = (0.45, 0.62, 1.0, 1)
    g.set(bsdf.inputs["Emission Color"], ramp.outputs["Color"])
    # blinds: the upper part of some windows is darker; brightness varies room to room
    tc = g.node("ShaderNodeTexCoord")
    zpos = g.math("FRACT", g.math("DIVIDE", g.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"]).outputs["Z"], 3.2))
    blind_h = g.math("ADD", 0.45, g.math("MULTIPLY", g.math("FRACT", g.math("MULTIPLY", rv, 13.7)), 0.45))
    blind = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.ramp(zpos, blind_h, g.math("ADD", blind_h, 0.02)), 0.75))
    level = g.math("ADD", 0.35, g.math("MULTIPLY", g.math("FRACT", g.math("MULTIPLY", rv, 3.9)), 0.65))
    g.set(bsdf.inputs["Emission Strength"],
          g.math("MULTIPLY", g.math("MULTIPLY", lit, strength * 1.1), g.math("MULTIPLY", blind, level)))
    return _haze(m)


def tower(coll, rnd, x, y, w, d, h, color, kind):
    wall = tex_mat(f"wall_{color}_{kind}", kind, color, tile=1.4 if kind == "corrugated" else 3.0, rough=0.75)
    trim = mat("trim", "painted_metal", "#3b3f45", wear=0.4, dirt=0.6, tile=3.0)
    glass, shop = glass_mat("glass"), glass_mat("shopglass", shop=True)
    z = 0.0
    tiers = rnd.choice([1, 2, 2, 3])
    bay = rnd.choice([3.4, 4.0, 4.6])                      # fewer, bigger windows
    balconies = rnd.random() < 0.3
    style = rnd.choice(["grid", "grid", "sparse", "sparse", "blank"])
    for t in range(tiers):
        th = h / tiers * (1.0 if t == 0 else rnd.uniform(0.6, 0.9))
        me = facade.tier_mesh("tier", w, d, th, rnd, bay=bay, storey=3.4, shop=(t == 0), balconies=balconies,
                              style=style)
        for m in (wall, glass, shop, trim):
            me.materials.append(m)
        ob = bpy.data.objects.new("tower", me)
        coll.objects.link(ob)
        ob.location = (x, y, z)
        z += th
        w, d = w * rnd.uniform(0.65, 0.85), d * rnd.uniform(0.65, 0.85)
    # rooftop: tanks, boxes, a mast
    metal = mat("roof_metal", "bare_metal", "#7d8288", rough=0.5, dirt=0.6, tile=3.0)
    for _ in range(rnd.randint(1, 3)):
        r = rnd.uniform(0.8, 1.6)
        box(coll, "tank", (r * 2, r * 2, r * 2.2), (x + rnd.uniform(-w / 3, w / 3), y + rnd.uniform(-d / 3, d / 3),
                                                     z + r * 1.1), metal, 0.05, shape="cylinder_z")
    if rnd.random() < 0.6:
        mh = rnd.uniform(3, 7)
        box(coll, "mast", (0.18, 0.18, mh), (x, y, z + mh / 2), metal, 0.02)
        box(coll, "beacon", (0.35, 0.35, 0.35), (x, y, z + mh + 0.2), emissive("beacon", "#ff4a3a", 12), 0.08)
    return z


def lamp(coll, x, y, rot=0.0, h=5.5):
    post = mat("lamp_post", "painted_metal", "#2f3a40", wear=0.5, dirt=0.5, tile=1.0)
    box(coll, "lamp_post", (0.22, 0.22, h), (x, y, h / 2), post, 0.03)
    arm = box(coll, "lamp_arm", (1.4, 0.18, 0.18), (x + 0.6 * math.cos(rot), y + 0.6 * math.sin(rot), h), post, 0.03)
    arm.rotation_euler.z = rot
    hx, hy = x + 1.2 * math.cos(rot), y + 1.2 * math.sin(rot)
    on = CFG["lamps"] > 0
    box(coll, "lamp_head", (0.7, 0.45, 0.22), (hx, hy, h - 0.12),
        emissive("lamp_glow", "#ffcf8a", 14) if on else mat("lamp_off", "plastic", "#d8d2c4", wear=0.1, dirt=0.3),
        0.04)
    if not on:
        return
    ld = bpy.data.lights.new("lamp", "SPOT")
    ld.energy = CFG["lamps"]
    ld.color = (1.0, 0.78, 0.5)
    ld.spot_size = math.radians(95)
    ld.spot_blend = 0.8
    ld.shadow_soft_size = 0.4
    ob = bpy.data.objects.new("lamp", ld)
    coll.objects.link(ob)
    ob.location = (hx, hy, h - 0.3)


def tree(coll, rnd, x, y, s=1.0):
    planter = tex_mat("planter", "concrete", "#a39d92", tile=1.5)
    bark = mat("bark_paint", "painted_metal", "#5a4030", wear=0.2, dirt=0.5, rough=0.8, tile=0.8)
    box(coll, "planter", (2.2 * s, 2.2 * s, 0.7 * s), (x, y, 0.35 * s), planter, 0.08)
    th = rnd.uniform(2.2, 3.0) * s
    box(coll, "trunk", (0.34 * s, 0.34 * s, th), (x, y, 0.7 * s + th / 2), bark, 0.06)
    greens = ["#4f8f3a", "#5fa045", "#3f7d36", "#73ad4e", "#4a8a44"]
    cz = 0.7 * s + th
    for k in range(rnd.randint(7, 10)):
        c = rnd.uniform(0.9, 1.6) * s
        g = greens[rnd.randrange(len(greens))]
        leaf = mat(f"leaf_{g}", "plastic", g, wear=0.0, dirt=0.15, rough=0.55, tile=1.0)
        ang = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.2, 1.0) * s
        box(coll, "leaves", (c, c, c * 0.8),
            (x + math.cos(ang) * r, y + math.sin(ang) * r, cz + rnd.uniform(-0.2, 1.2) * s),
            leaf, c * 0.32, rot=rnd.uniform(0, 1.2), shape="rounded_box")


def crates(coll, rnd, x, y, along=(1, 0)):
    """A stack against a wall: a bottom row of 2-3 crates, and maybe one crate sitting squarely on top of one."""
    wood = mat("crate", "painted_metal", rnd.choice(["#8a5a3c", "#5f7f86", "#b98e5d"]), wear=0.6, dirt=0.6, tile=1.2)
    ux, uy = along
    s0 = rnd.uniform(0.9, 1.1)
    n = rnd.randint(2, 3)
    for k in range(n):
        box(coll, "crate", (s0, s0, s0), (x + ux * k * (s0 + 0.05), y + uy * k * (s0 + 0.05), s0 / 2), wood, 0.04,
            rot=rnd.uniform(-0.06, 0.06))
    if rnd.random() < 0.7:
        k = rnd.randrange(n)
        t = s0 * 0.85
        box(coll, "crate", (t, t, t), (x + ux * k * (s0 + 0.05), y + uy * k * (s0 + 0.05), s0 + t / 2), wood, 0.04,
            rot=rnd.uniform(-0.15, 0.15))


def pipes(coll, x0, x1, y, z):
    metal = mat("pipe", "painted_metal", "#6b4a3a", wear=0.6, dirt=0.7, tile=1.0)
    L = abs(x1 - x0)
    box(coll, "pipe", (L, 0.45, 0.45), ((x0 + x1) / 2, y, z), metal, 0.05, shape="cylinder_x")
    box(coll, "pipe", (L, 0.3, 0.3), ((x0 + x1) / 2, y, z + 0.7), metal, 0.05, shape="cylinder_x")
    for xs in range(int(min(x0, x1)) + 2, int(max(x0, x1)), 4):
        box(coll, "pipe_clamp", (0.25, 0.6, 1.4), (xs, y, z + 0.35), metal, 0.03)


# ------------------------------------------------------------------ the square
def sky(sc):
    """Sky dome: horizon -> sky colour -> zenith, plus soft clouds by day and stars by night."""
    w = bpy.data.worlds.new("sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    hor, mid_c, zen = CFG["sky"]
    cr = ramp.color_ramp
    day = CFG["sun"][0] > 2
    # world "Generated" is the view direction (-1..1), so z = 0 is the horizon and z = 1 straight up
    cr.elements[0].position, cr.elements[0].color = 0.0, hor + (1,)
    cr.elements[1].position, cr.elements[1].color = (0.45 if day else 0.35), zen + (1,)
    mid = cr.elements.new(0.06 if day else 0.04)
    mid.color = mid_c + (1,)
    col = ramp.outputs["Color"]

    def node(t, **kw):
        n = nt.nodes.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def mix(fac, a, b_):
        m = node("ShaderNodeMix", data_type="RGBA")
        nt.links.new(fac, m.inputs["Factor"])
        nt.links.new(a, m.inputs["A"]) if not isinstance(a, tuple) else setattr(m.inputs["A"], "default_value", a)
        if isinstance(b_, tuple):
            m.inputs["B"].default_value = b_
        else:
            nt.links.new(b_, m.inputs["B"])
        return m.outputs["Result"]

    above = node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    nt.links.new(sep.outputs["Z"], above.inputs["Value"])
    above.inputs["From Min"].default_value = 0.01
    above.inputs["From Max"].default_value = 0.09
    if day:
        mp = node("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (2.2, 2.2, 9.0)          # flattened, wide clouds
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nz = node("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 2.5
        nz.inputs["Detail"].default_value = 6.0
        nz.inputs["Roughness"].default_value = 0.55
        nt.links.new(mp.outputs[0], nz.inputs["Vector"])
        cm = node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        nt.links.new(nz.outputs["Fac"], cm.inputs["Value"])
        cm.inputs["From Min"].default_value = 0.52
        cm.inputs["From Max"].default_value = 0.68
        m = node("ShaderNodeMath", operation="MULTIPLY")
        nt.links.new(cm.outputs["Result"], m.inputs[0])
        nt.links.new(above.outputs["Result"], m.inputs[1])
        col = mix(m.outputs[0], col, (1.0, 0.97, 0.92, 1))
    else:
        mp = node("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (700, 700, 700)
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        fl = node("ShaderNodeVectorMath", operation="FLOOR")
        nt.links.new(mp.outputs[0], fl.inputs[0])
        wn = node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
        nt.links.new(fl.outputs[0], wn.inputs["Vector"])
        st = node("ShaderNodeMath", operation="GREATER_THAN")
        nt.links.new(wn.outputs["Value"], st.inputs[0])
        st.inputs[1].default_value = 0.9975
        m = node("ShaderNodeMath", operation="MULTIPLY")
        nt.links.new(st.outputs[0], m.inputs[0])
        nt.links.new(above.outputs["Result"], m.inputs[1])
        m2 = node("ShaderNodeMath", operation="MULTIPLY")
        nt.links.new(m.outputs[0], m2.inputs[0])
        m2.inputs[1].default_value = 6.0
        add = node("ShaderNodeMix", data_type="RGBA", blend_type="ADD")
        nt.links.new(m2.outputs[0], add.inputs["Factor"])
        nt.links.new(col, add.inputs["A"])
        add.inputs["B"].default_value = (0.8, 0.85, 1.0, 1)
        col = add.outputs["Result"]
    nt.links.new(col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = CFG["sky_strength"]
    sc.world = w
    energy, color, elev, heading = CFG["sun"]
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = energy
    sun.color = color
    sun.angle = math.radians(CFG.get("sun_angle", 2.5))
    ob = bpy.data.objects.new("sun", sun)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(90 - elev), 0, math.radians(heading))


def _drop_material():
    """Raindrop: mostly see-through; picks up light only where a lamp or window is near, like real drizzle."""
    m = bpy.data.materials.get("w_drop")
    if m:
        return m
    m = bpy.data.materials.new("w_drop")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tl = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tl.inputs["Color"].default_value = (0.9, 0.95, 1.0, 1)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.05
    lit = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tl.outputs[0], lit.inputs[0])
    nt.links.new(gl.outputs[0], lit.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.55
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(lit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def rain(sc, cam, target, amount=1.0):
    """Drizzle as real 3D drops (Geometry Nodes): points scattered through the space in front of the camera, each
    a thin streak (length = fall distance during the shutter), falling with the frame and wrapping at the bottom.
    Drops are translucent, so they show where light hits them: around lamps and windows. Only for night_rain."""
    if not CFG["wet"]:
        return
    target = Vector(target)
    d = (target - cam.location).length
    near, far = 0.35 * d, min(3.0 * d + 8.0, 70.0)
    half_w = far * math.tan(math.radians(34)) + 1.0
    top = max(target.z * 2.5 + 3.0, 6.0)
    volume = (2 * half_w) * (far - near) * top
    count = int(min(90000, max(4000, volume * 18 * amount)))
    drop_len = 0.09 if d < 4 else 0.16                    # longer streaks read better in wide shots

    ng = bpy.data.node_groups.new("rain_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, L = ng.nodes, ng.links
    pts = n.new("GeometryNodePoints")
    pts.inputs["Count"].default_value = count
    rnd = n.new("FunctionNodeRandomValue")
    rnd.data_type = "FLOAT_VECTOR"
    vmin = next(sk for sk in rnd.inputs if sk.name == "Min" and sk.type == "VECTOR")
    vmax = next(sk for sk in rnd.inputs if sk.name == "Max" and sk.type == "VECTOR")
    vmin.default_value = (-half_w, near, 0.0)
    vmax.default_value = (half_w, far, top)
    L.new(next(o for o in rnd.outputs if o.type == "VECTOR" and o.enabled), pts.inputs["Position"])
    # fall: z = top - ((top - z0 + t * speed) mod top)
    pos = n.new("GeometryNodeInputPosition")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(pos.outputs[0], sep.inputs[0])
    st = n.new("GeometryNodeInputSceneTime")

    def mth(op, a, b):
        m = n.new("ShaderNodeMath")
        m.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                L.new(v, m.inputs[i])
        return m.outputs[0]

    fall = mth("MULTIPLY", st.outputs["Seconds"], 6.5)          # drizzle falls about 6.5 m/s
    z = mth("SUBTRACT", top, mth("FLOORED_MODULO", mth("ADD", mth("SUBTRACT", top, sep.outputs["Z"]), fall), top))
    comb = n.new("ShaderNodeCombineXYZ")
    L.new(sep.outputs["X"], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])
    L.new(z, comb.inputs["Z"])
    setp = n.new("GeometryNodeSetPosition")
    L.new(pts.outputs[0], setp.inputs["Geometry"])
    L.new(comb.outputs[0], setp.inputs["Position"])
    cyl = n.new("GeometryNodeMeshCylinder")
    cyl.inputs["Vertices"].default_value = 4
    cyl.inputs["Radius"].default_value = 0.0011 if d < 4 else 0.0022
    cyl.inputs["Depth"].default_value = drop_len
    inst = n.new("GeometryNodeInstanceOnPoints")
    L.new(setp.outputs[0], inst.inputs["Points"])
    L.new(cyl.outputs["Mesh"], inst.inputs["Instance"])
    inst.inputs["Rotation"].default_value = (0.0, 0.1, 0.0)    # slight slant
    smat = n.new("GeometryNodeSetMaterial")
    smat.inputs["Material"].default_value = _drop_material()
    L.new(inst.outputs[0], smat.inputs["Geometry"])
    out = n.new("NodeGroupOutput")
    L.new(smat.outputs[0], out.inputs[0])

    me = bpy.data.meshes.new("rain")
    ob = bpy.data.objects.new("rain", me)
    sc.collection.objects.link(ob)
    mod = ob.modifiers.new("rain", "NODES")
    mod.node_group = ng
    # the rain box sits in front of the camera, turned with the camera's heading
    fwd = (target - cam.location)
    heading = math.atan2(fwd.x, fwd.y)
    ob.location = (cam.location.x, cam.location.y, 0.0)
    ob.rotation_euler.z = -heading
    ob.visible_shadow = False
    ob.visible_diffuse = False


def ripples(g, coord, puddle):
    """Rain rings in the puddles: one ring per Voronoi cell, growing and fading on its own clock."""
    vor = g.node("ShaderNodeTexVoronoi", Vector=coord, Scale=3.5)
    dist = vor.outputs["Distance"]
    phase = g.node("ShaderNodeSeparateColor", Color=vor.outputs["Color"]).outputs[0]
    clock = g.node("ShaderNodeValue")
    fc = clock.outputs[0].driver_add("default_value")
    fc.driver.expression = "frame / 24.0"
    t = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", clock.outputs[0], 1.3), phase))
    r = g.math("MULTIPLY", t, 0.5)
    ring = g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", dist, r)), 0.0, 0.035))
    ring = g.math("MULTIPLY", ring, g.math("SUBTRACT", 1.0, t))
    return g.math("MULTIPLY", ring, puddle)


class Plan:
    """Keeps the footprints of everything placed, so props never sit inside buildings or each other."""

    def __init__(self):
        self.boxes = []

    def free(self, x0, y0, x1, y1, pad=0.0):
        for (a0, b0, a1, b1, name) in self.boxes:
            if x0 - pad < a1 and x1 + pad > a0 and y0 - pad < b1 and y1 + pad > b0:
                return False
        return True

    def add(self, x0, y0, x1, y1, name):
        self.boxes.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), name))


ROAD_Z = -0.15          # roads sit one kerb below the sidewalks and the square (top of sidewalk/square = 0)
SQ_X, SQ_Y0, SQ_Y1 = 18.0, -12.0, 20.0     # the square: |x| < 18, -12 < y < 20
ROAD_W, WALK_W = 10.0, 4.0
BACK_STREET = 5.0       # half width of the street that runs away from the square, centred on x = 0


def build(sc, seed=7, tod="dusk"):
    global CFG, HAZE
    CFG = TOD[tod]
    HAZE = CFG["haze"]
    rnd = random.Random(seed)
    plan = Plan()
    coll = bpy.data.collections.new("gridhaven")
    sc.collection.children.link(coll)
    sky(sc)
    asphalt = tex_mat("asphalt", "asphalt", tile=3.0, rough=0.85, bump=0.5, wet=True)
    walk = tex_mat("sidewalk", "concrete", "#8d8a84", tile=2.0, rough=0.8, wet=True)
    slab = tex_mat("slab", "concrete", "#77746e", tile=2.5, rough=0.8, wet=True)
    slab2 = tex_mat("slab2", "concrete", "#6a6863", tile=2.5, rough=0.8, wet=True)
    kerb = tex_mat("kerb", "concrete", "#b5afa5", tile=1.5)
    paint = mat("road_paint", "plastic", "#e8e4d8", wear=0.5, dirt=0.4, rough=0.7, tile=1.0)

    box(coll, "road", (500, 500, 0.2), (0, 100, ROAD_Z - 0.1), asphalt, 0)
    # the square: slabs with joints, a kerb around it
    for i in range(int(-SQ_X), int(SQ_X), 3):
        for j in range(int(SQ_Y0), int(SQ_Y1), 3):
            m = slab if (i * 7 + j * 3) % 5 else slab2
            box(coll, "slab", (2.94, 2.94, 0.15), (i + 1.5, j + 1.5, -0.075), m, 0.01)
    for (cx, cy, sx, sy) in ((0, SQ_Y0, 2 * SQ_X + 0.4, 0.4), (0, SQ_Y1, 2 * SQ_X + 0.4, 0.4),
                             (-SQ_X, (SQ_Y0 + SQ_Y1) / 2, 0.4, SQ_Y1 - SQ_Y0), (SQ_X, (SQ_Y0 + SQ_Y1) / 2, 0.4, SQ_Y1 - SQ_Y0)):
        box(coll, "kerb", (sx, sy, 0.2), (cx, cy, -0.05), kerb, 0.04)

    # building lots: (centre x, centre y, width, depth) with fronts on the sidewalks
    back_front = SQ_Y1 + ROAD_W + WALK_W            # y of the back buildings' front faces
    side_front = SQ_X + ROAD_W + WALK_W             # |x| of the side buildings' front faces
    lots = []
    # back row, split by the street that runs away from the square
    for side in (-1, 1):
        x = BACK_STREET + WALK_W
        while x < 46:
            w = rnd.uniform(10, 14)
            lots.append((side * (x + w / 2), back_front + 6, w, 12))
            x += w + rnd.uniform(2.5, 4.0)             # an alley between buildings
    # side rows
    for side in (-1, 1):
        y = SQ_Y0 - 8
        while y < back_front - 4:
            d = rnd.uniform(10, 13)
            if y + d > back_front - 2:
                break
            lots.append((side * (side_front + 6), y + d / 2, 12, d))
            y += d + rnd.uniform(2.5, 4.0)
    # buildings along the back street, receding to the horizon
    y = back_front + 16
    while y < 220:
        d = rnd.uniform(12, 18)
        for side in (-1, 1):
            w = rnd.uniform(10, 14)
            lots.append((side * (BACK_STREET + WALK_W + w / 2), y + d / 2, w, d))
        y += d + rnd.uniform(3, 6)
    for (x, y, w, d) in lots:
        far = abs(y) > 90
        h = rnd.uniform(14, 34) if not far else rnd.uniform(25, 60)
        tower(coll, rnd, x, y, w, d, h, rnd.choice(PALETTE), rnd.choice(["concrete", "concrete", "corrugated"]))
        plan.add(x - w / 2, y - d / 2, x + w / 2, y + d / 2, "building")
    # sidewalks: back (both sides of the back street), sides, and along the back street
    box(coll, "walk", (2 * 60, WALK_W, 0.15), (0, back_front - WALK_W / 2, -0.075), walk, 0.02)
    for side in (-1, 1):
        box(coll, "walk", (WALK_W, back_front - SQ_Y0 + 20, 0.15),
            (side * (side_front - WALK_W / 2), (back_front + SQ_Y0 - 20) / 2, -0.075), walk, 0.02)
        box(coll, "walk", (WALK_W, 200, 0.15), (side * (BACK_STREET + WALK_W / 2), back_front + 100, -0.075), walk, 0.02)
    # road paint: centre dashes on the ring road and the back street, a zebra crossing at the street mouth
    yc = SQ_Y1 + ROAD_W / 2
    for x in range(-44, 46, 4):
        box(coll, "dash", (2.0, 0.16, 0.02), (x, yc, ROAD_Z + 0.01), paint, 0)
    for side in (-1, 1):
        xc = side * (SQ_X + ROAD_W / 2)
        for y in range(int(SQ_Y0 - 10), int(back_front), 4):
            box(coll, "dash", (0.16, 2.0, 0.02), (xc, y, ROAD_Z + 0.01), paint, 0)
    for y in range(int(back_front + 4), 220, 5):
        box(coll, "dash", (0.16, 2.4, 0.02), (0, y, ROAD_Z + 0.01), paint, 0)
    for k in range(-4, 5):
        box(coll, "zebra", (0.55, 3.2, 0.02), (k * 1.1, SQ_Y1 + 2.0, ROAD_Z + 0.01), paint, 0)

    # the Big Board: flat on the face of the first right-hand back building
    rb = min((l for l in lots if l[0] > 0 and abs(l[1] - (back_front + 6)) < 0.5), key=lambda l: l[0])
    bx, by = rb[0], rb[1] - rb[3] / 2
    frame = mat("board_frame", "painted_metal", "#2a2f36", wear=0.3, dirt=0.4, tile=2.0)
    box(coll, "board_frame", (8.5, 0.4, 5.0), (bx, by - 0.2, 11), frame, 0.08)
    box(coll, "board", (7.8, 0.1, 4.4), (bx, by - 0.42, 11),
        emissive("board", "#2f63b0", 0.7) if CFG["lamps"] > 0 else mat("board_off", "plastic", "#15181d", wear=0.0,
                                                                         dirt=0.2, rough=0.15), 0.02)

    # lamps on the sidewalks, arms over the road
    for x in (-30, -12, 12, 30):
        if plan.free(x - 0.3, back_front - 3.2, x + 0.3, back_front - 2.6):
            lamp(coll, x, back_front - 2.9, -math.pi / 2)
            plan.add(x - 0.3, back_front - 3.2, x + 0.3, back_front - 2.6, "lamp")
    for side in (-1, 1):
        for y in (-6, 8):
            lx = side * (side_front - 1.0)
            lamp(coll, lx, y, math.pi if side > 0 else 0.0)
            plan.add(lx - 0.3, y - 0.3, lx + 0.3, y + 0.3, "lamp")
    # lamps along the back street
    for y in range(int(back_front + 12), 200, 15):
        for side in (-1, 1):
            lx = side * (BACK_STREET + WALK_W - 0.8)
            if plan.free(lx - 0.3, y - 0.3, lx + 0.3, y + 0.3, pad=0.5):
                lamp(coll, lx, y, math.pi if side > 0 else 0.0)
                plan.add(lx - 0.3, y - 0.3, lx + 0.3, y + 0.3, "lamp")
    # trees: on the square's back corners and along the back street, clear of everything
    spots = [(-14, 15), (14, 15), (-14, -8), (14, -8)]
    spots += [(side * (BACK_STREET + 1.6), y) for side in (-1, 1) for y in (back_front + 6, back_front + 22)]
    for (x, y) in spots:
        if plan.free(x - 1.2, y - 1.2, x + 1.2, y + 1.2, pad=2.0):
            tree(coll, rnd, x, y, rnd.uniform(0.9, 1.15) if abs(x) > 8 else 0.75)
            plan.add(x - 1.2, y - 1.2, x + 1.2, y + 1.2, "tree")
    # crates against building fronts (on the sidewalk, touching the wall)
    for (x, y, w, d) in lots:
        if abs(y - (back_front + 6)) < 0.5 and rnd.random() < 0.5:
            cx, cy = x - w / 2 + 1.0, y - d / 2 - 0.6
            if plan.free(cx - 0.6, cy - 0.6, cx + 3.4, cy + 0.6):
                crates(coll, rnd, cx, cy, along=(1, 0))
                plan.add(cx - 0.6, cy - 0.6, cx + 3.4, cy + 0.6, "crates")
    # benches on the square
    bench = mat("bench", "painted_metal", "#3f5a4a", wear=0.4, dirt=0.4, tile=1.0)
    for (x, y) in ((-10, 17.2), (10, 17.2)):
        box(coll, "bench_seat", (2.4, 0.6, 0.12), (x, y, 0.45), bench, 0.03)
        box(coll, "bench_back", (2.4, 0.12, 0.5), (x, y + 0.3, 0.75), bench, 0.03)
        for dx in (-1.0, 1.0):
            box(coll, "bench_leg", (0.12, 0.5, 0.45), (x + dx, y, 0.22), bench, 0.02)
    print(f"gridhaven: {len(lots)} buildings, {len(plan.boxes) - len(lots)} props placed clear of buildings")
    return coll
