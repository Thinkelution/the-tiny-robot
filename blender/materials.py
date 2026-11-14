"""Layered PBR materials for boxy robots and sets (Cycles quality; EEVEE falls back gracefully).

kinds: painted_metal, bare_metal, rubber, plastic, glass, emissive, screen
Every painted material gets: fine paint bump, roughness breakup, edge wear (bare metal shows through on edges),
dirt in crevices (AO), and light scratches. `wear` and `dirt` (0..1) scale those layers.
Image textures (generated texture sets) plug in through `tex` = {"color": path, "rough": path, "normal": path}
with box projection, so UVs never matter for them.
"""
import bpy


def hex_rgb(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)


class G:
    """Tiny node-graph helper."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.n = self.nt.nodes
        self.x = -1600

    def node(self, kind, **inputs):
        nd = self.n.new(kind)
        nd.location = (self.x, (len(self.n) % 12) * -180)
        self.x += 60
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(nd, k[1:], v)
            else:
                self.set(nd.inputs[k], v)
        return nd

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, clamp=False):
        nd = self.node("ShaderNodeMath", _operation=op, _use_clamp=clamp)
        self.set(nd.inputs[0], a)
        if b is not None:
            self.set(nd.inputs[1], b)
        return nd.outputs[0]

    def mix(self, fac, a, b):
        nd = self.node("ShaderNodeMix", _data_type="RGBA")
        self.set(nd.inputs["Factor"], fac)
        self.set(nd.inputs["A"], a)
        self.set(nd.inputs["B"], b)
        return nd.outputs["Result"]

    def mixf(self, fac, a, b):
        nd = self.node("ShaderNodeMix", _data_type="FLOAT")
        self.set(nd.inputs["Factor"], fac)
        self.set(nd.inputs["A"], a)
        self.set(nd.inputs["B"], b)
        return nd.outputs["Result"]

    def ramp(self, val, lo, hi):
        """smoothstep-ish remap of val from [lo, hi] to [0, 1]."""
        nd = self.node("ShaderNodeMapRange", _interpolation_type="SMOOTHSTEP", _clamp=True)
        self.set(nd.inputs["Value"], val)
        self.set(nd.inputs["From Min"], lo)
        self.set(nd.inputs["From Max"], hi)
        return nd.outputs["Result"]


def _noise(g, coord, scale, detail=6.0, rough=0.6, dist=0.0):
    return g.node("ShaderNodeTexNoise", Vector=coord, Scale=scale, Detail=detail, Roughness=rough,
                  Distortion=dist).outputs["Fac"]


def _image_box(g, path, coord, non_color=False, blend=0.25):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    nd = g.node("ShaderNodeTexImage", Vector=coord, _projection="BOX", _projection_blend=blend)
    nd.image = img
    return nd


def make(spec: dict) -> bpy.types.Material:
    """spec: {id, kind, color, roughness, metallic, wear, dirt, emission, pattern, pattern_color, tex, tex_scale}"""
    name = spec["id"]
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    g = G(mat)
    for nd in list(g.n):
        if nd.type != "OUTPUT_MATERIAL":
            g.n.remove(nd)
    out = next(nd for nd in g.n if nd.type == "OUTPUT_MATERIAL")
    out.location = (600, 0)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    g.nt.links.new(bsdf.outputs[0], out.inputs["Surface"])

    kind = spec.get("kind", "painted_metal")
    if spec.get("textured", True) and kind in ("painted_metal", "bare_metal", "plastic", "rubber", "screen"):
        import texmat
        if texmat.available():
            texmat.build(mat, g, spec, bsdf, hex_rgb)
            return mat
    color = hex_rgb(spec.get("color", "#9a9a9a"))
    rough = spec.get("roughness", 0.45)
    wear = spec.get("wear", 0.3)
    dirt = spec.get("dirt", 0.3)
    texcoord = g.node("ShaderNodeTexCoord")
    obj_co = texcoord.outputs["Object"]
    scale = spec.get("tex_scale", 1.0)
    co = g.node("ShaderNodeMapping", Vector=obj_co, Scale=(scale, scale, scale)).outputs[0]

    if kind == "emissive":
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = spec.get("emission", 3.0)
        bsdf.inputs["Roughness"].default_value = 0.3
        return mat
    if kind == "glass":
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        return mat
    if kind == "screen":      # dark glossy face glass with a faint inner glow
        bsdf.inputs["Base Color"].default_value = (0.006, 0.008, 0.01, 1)
        bsdf.inputs["Roughness"].default_value = 0.12
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.04
        glow = hex_rgb(spec.get("glow", "#103040"))
        glow = tuple(c * 0.12 for c in glow[:3]) + (1,)   # glass stays dark whatever glow colour a spec asks for
        bsdf.inputs["Emission Color"].default_value = glow
        bsdf.inputs["Emission Strength"].default_value = 0.05   # faint: the glass must read dark so the eyes pop
        smudge = _noise(g, co, 9.0, 4, 0.5)
        g.set(bsdf.inputs["Roughness"], g.mixf(g.ramp(smudge, 0.6, 0.8), 0.06, 0.16))
        return mat

    # ---- base layer
    tex = spec.get("tex") or {}
    if tex.get("color"):
        base = _image_box(g, tex["color"], co).outputs["Color"]
        base = g.mix(0.35, base, color) if spec.get("tint", True) else base
    else:
        # large-scale tonal variation keeps flat colours from looking CG
        var = _noise(g, co, 2.5, 3, 0.5)
        base = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", var, 0.5), 0.5),
                     color, tuple(c * 0.78 for c in color[:3]) + (1,))
    pat = spec.get("pattern", "none")
    if pat in ("stripes", "hazard"):
        wave = g.node("ShaderNodeTexWave", Vector=co, Scale=spec.get("pattern_scale", 3.0),
                      _wave_type="BANDS", _bands_direction="DIAGONAL" if pat == "hazard" else "Z")
        band = g.ramp(wave.outputs["Fac"], 0.48, 0.52)
        base = g.mix(band, base, hex_rgb(spec.get("pattern_color", "#202020")))

    metallic = spec.get("metallic", 1.0 if kind == "bare_metal" else 0.0)
    r_noise = _noise(g, co, 14.0, 8, 0.65)
    rough_s = g.mixf(r_noise, rough * 0.8, min(1.0, rough * 1.25))
    if tex.get("rough"):
        rough_s = _image_box(g, tex["rough"], co, non_color=True).outputs["Color"]

    if kind in ("rubber",):
        bsdf.inputs["Base Color"].default_value = color
        g.set(bsdf.inputs["Roughness"], g.mixf(r_noise, 0.7, 0.9))
        bump = g.node("ShaderNodeBump", Strength=0.15, Height=_noise(g, co, 60.0, 4, 0.5))
        g.set(bsdf.inputs["Normal"], bump.outputs[0])
        return mat

    # ---- edge mask (Cycles Bevel node): rounded normal vs true normal differs only near edges
    bev = g.node("ShaderNodeBevel", Radius=spec.get("edge_radius", 0.005), _samples=8)
    geo = g.node("ShaderNodeNewGeometry")
    dot = g.node("ShaderNodeVectorMath", _operation="DOT_PRODUCT")
    g.set(dot.inputs[0], bev.outputs[0])
    g.set(dot.inputs[1], geo.outputs["Normal"])
    edge = g.math("SUBTRACT", 1.0, dot.outputs["Value"])
    edge = g.math("MULTIPLY", edge, 25.0, clamp=True)
    chip = _noise(g, co, 22.0, 10, 0.75, 0.3)
    edge = g.ramp(g.math("SUBTRACT", g.math("ADD", edge, chip), 1.0 - wear * 0.6), 0.25, 0.4)
    edge = g.math("MULTIPLY", edge, min(1.0, wear * 1.6), clamp=True)

    # ---- dirt in crevices (AO) broken up by noise
    ao = g.node("ShaderNodeAmbientOcclusion", Distance=0.06, _samples=8)
    cav = g.math("SUBTRACT", 1.0, ao.outputs["AO"])
    grime_n = _noise(g, co, 5.0, 6, 0.6)
    grime = g.math("MULTIPLY", g.ramp(g.math("ADD", cav, g.math("MULTIPLY", grime_n, 0.6)), 0.35, 0.9), dirt, clamp=True)
    # streaks running down (rain/oil) on painted surfaces
    streak_co = g.node("ShaderNodeMapping", Vector=co, Scale=(18.0, 18.0, 1.2)).outputs[0]
    streak = g.math("MULTIPLY", g.ramp(_noise(g, streak_co, 3.0, 4, 0.5), 0.55, 0.75), dirt * 0.5)
    grime = g.math("MAXIMUM", grime, streak)

    bare = (0.55, 0.55, 0.56, 1)
    col = g.mix(edge, base, bare) if kind == "painted_metal" else base
    dirt_col = (0.045, 0.035, 0.025, 1)
    col = g.mix(g.math("MULTIPLY", grime, 0.85), col, dirt_col)
    g.set(bsdf.inputs["Base Color"], col)

    met = g.mixf(edge, metallic, 1.0) if kind == "painted_metal" else metallic
    g.set(bsdf.inputs["Metallic"], met)
    rgh = g.mixf(edge, rough_s, 0.3)
    rgh = g.mixf(grime, rgh, 0.9)
    g.set(bsdf.inputs["Roughness"], rgh)
    if kind == "plastic":
        bsdf.inputs["Coat Weight"].default_value = 0.3

    # ---- bump: orange-peel paint + scratches + chipped paint step
    scratch_co = g.node("ShaderNodeMapping", Vector=co, Scale=(1.0, 1.0, 40.0), Rotation=(0.3, 0.8, 0.2)).outputs[0]
    scratch = g.ramp(_noise(g, scratch_co, 30.0, 2, 0.4), 0.62, 0.66)
    scratch = g.math("MULTIPLY", scratch, wear)
    peel = _noise(g, co, 180.0, 2, 0.5)
    height = g.math("ADD", g.math("MULTIPLY", peel, 0.15), g.math("MULTIPLY", scratch, -0.6))
    if kind == "painted_metal":
        height = g.math("ADD", height, g.math("MULTIPLY", edge, -0.5))
    bump = g.node("ShaderNodeBump", Strength=0.25, Distance=0.002, Height=height)
    if tex.get("normal"):
        nimg = _image_box(g, tex["normal"], co, non_color=True)
        nmap = g.node("ShaderNodeNormalMap", Color=nimg.outputs["Color"], Strength=0.8)
        g.set(bump.inputs["Normal"], nmap.outputs[0])
    g.set(bsdf.inputs["Normal"], bump.outputs[0])
    return mat
