"""Studio texture-set materials: generated photo textures (textures/lib) layered into PBR, mapped through UVs.

Used by materials.make() for painted_metal, bare_metal, plastic, rubber and screen when the library exists.
Layers for painted metal, bottom to top:
  base   - the material colour modulated by the worn-paint photo (tonal variation, specks, repaint patches)
  wear   - chipped-paint mask + Cycles edge mask reveal brushed steel; scratches cut through the paint
  grime  - rust/dirt streak texture runs down the faces; AO puts dirt into crevices
  relief - normal map from the paint photo, plus a bump step at chip edges
Every object gets a random UV offset (Object Info > Random) so parts never repeat the same pattern.
`tex_tile` (metres per texture repeat) scales the detail to the character's size.
"""
import json
from pathlib import Path

import bpy

LIB = Path(__file__).resolve().parent.parent / "textures" / "lib"
META = json.loads((LIB / "meta.json").read_text()) if (LIB / "meta.json").exists() else {}


def available():
    return bool(META)


def _img(g, tid, kind, coord, non_color=False):
    path = LIB / tid / f"{kind}.png"
    img = bpy.data.images.load(str(path), check_existing=True)
    # detail and mask textures are read raw, so their values match meta.json (measured on the file's own values);
    # only the grime photo is used as a real colour
    if non_color or tid != "grime":
        img.colorspace_settings.name = "Non-Color"
    nd = g.node("ShaderNodeTexImage", Vector=coord)
    nd.image = img
    nd.interpolation = "Cubic"
    return nd


def _lum(g, color_sock):
    return g.node("ShaderNodeRGBToBW", Color=color_sock).outputs[0]


def _detail(g, color_sock, tid, contrast):
    """1 + (lum - mean) * contrast: a multiplier centred on 1."""
    m = META[tid]["mean_lum"]
    return g.math("ADD", 1.0, g.math("MULTIPLY", g.math("SUBTRACT", _lum(g, color_sock), m), contrast))


def _uv(g, tile, seed_scale=(17.3, 9.7)):
    uv = g.node("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    rnd = g.node("ShaderNodeObjectInfo").outputs["Random"]
    off = g.node("ShaderNodeCombineXYZ", X=g.math("MULTIPLY", rnd, seed_scale[0]),
                 Y=g.math("MULTIPLY", rnd, seed_scale[1]))
    s = 1.0 / tile
    mp = g.node("ShaderNodeMapping", Vector=uv.outputs["UV"], Location=off.outputs[0], Scale=(s, s, s))
    return mp.outputs[0]


def _hue_is_gold(rgb):
    r, gg, b = rgb[:3]
    return r > gg > b and (r - b) > 0.15 * max(r, 1e-3)


def build(mat, g, spec, bsdf, hex_rgb):
    kind = spec.get("kind", "painted_metal")
    color = hex_rgb(spec.get("color", "#9a9a9a"))
    rough = spec.get("roughness", 0.45)
    wear = spec.get("wear", 0.3)
    dirt = spec.get("dirt", 0.3)
    tile = spec.get("tex_tile", 0.5)
    co = _uv(g, tile)

    if kind == "screen":
        bsdf.inputs["Base Color"].default_value = (0.006, 0.008, 0.01, 1)
        bsdf.inputs["Coat Weight"].default_value = 1.0
        smudge = _lum(g, _img(g, "glass_smudge", "color", _uv(g, tile * 0.6), True).outputs["Color"])
        sm = g.ramp(smudge, 0.03, 0.16)
        g.set(bsdf.inputs["Roughness"], g.mixf(sm, 0.05, 0.35))
        g.set(bsdf.inputs["Coat Roughness"], g.mixf(sm, 0.03, 0.3))
        glow = hex_rgb(spec.get("glow", "#103040"))
        bsdf.inputs["Emission Color"].default_value = tuple(c * 0.12 for c in glow[:3]) + (1,)
        bsdf.inputs["Emission Strength"].default_value = 0.05
        return

    if kind == "rubber":
        rc = _img(g, "rubber", "color", co).outputs["Color"]
        det = _detail(g, rc, "rubber", 2.5)
        g.set(bsdf.inputs["Base Color"], _mul(g, color, det))
        g.set(bsdf.inputs["Roughness"], g.math("ADD", 0.72, g.math("MULTIPLY", _lum(g, rc), 0.6)))
        nm = g.node("ShaderNodeNormalMap", Color=_img(g, "rubber", "normal", co, True).outputs["Color"], Strength=0.8)
        g.set(bsdf.inputs["Normal"], nm.outputs[0])
        return

    if kind == "bare_metal":
        gold = _hue_is_gold(color)
        tid = "brass_old" if gold else "metal_brushed"
        mc = _img(g, tid, "color", co).outputs["Color"]
        det = _detail(g, mc, tid, 2.2 if gold else 1.6)
        base = _mul(g, color, det)
        grime_c = _img(g, "grime", "color", _uv(g, tile * 3.2, (5.1, 3.3))).outputs["Color"]
        base = _grime(g, base, grime_c, dirt * 0.45)
        g.set(bsdf.inputs["Base Color"], base)
        bsdf.inputs["Metallic"].default_value = 1.0
        g.set(bsdf.inputs["Roughness"], g.math("ADD", rough * 0.8, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, det), 1.2)))
        nm = g.node("ShaderNodeNormalMap", Color=_img(g, tid, "normal", co, True).outputs["Color"], Strength=0.5)
        g.set(bsdf.inputs["Normal"], nm.outputs[0])
        return

    # ---------------- painted metal / plastic
    tid = "paint_worn" if (kind == "painted_metal" and wear >= 0.25) else "paint_clean"
    pc = _img(g, tid, "color", co).outputs["Color"]
    det = _detail(g, pc, tid, 7.0 if tid == "paint_worn" else 4.0)
    # broad tonal variation across a part (fade, sun-bleach) so flat colours never look CG
    broad = g.node("ShaderNodeTexNoise", Vector=co, Scale=0.35, Detail=2.0, Roughness=0.5).outputs["Fac"]
    det = g.math("MULTIPLY", det, g.math("ADD", 0.78, g.math("MULTIPLY", broad, 0.2)))   # paint sits a little deep
    base = _mul(g, color, det)
    pat = spec.get("pattern", "none")
    if pat in ("stripes", "hazard"):
        oco = g.node("ShaderNodeTexCoord").outputs["Object"]
        wave = g.node("ShaderNodeTexWave", Vector=oco, Scale=spec.get("pattern_scale", 3.0),
                      _wave_type="BANDS", _bands_direction="DIAGONAL" if pat == "hazard" else "Z")
        band = g.ramp(wave.outputs["Fac"], 0.48, 0.52)
        base = g.mix(band, base, _mul(g, hex_rgb(spec.get("pattern_color", "#202020")), det))

    # wear: chips + edges reveal bare steel, scratches cut through the paint
    metal_c = _img(g, "metal_brushed", "color", co).outputs["Color"]
    bare = _mul(g, (0.62, 0.62, 0.63, 1), _detail(g, metal_c, "metal_brushed", 1.6))
    chips = g.ramp(_lum(g, _img(g, "chips", "color", _uv(g, tile * 0.55, (3.7, 11.1)), True).outputs["Color"]), 0.45, 0.6)
    # chips cluster in patches (knocks and wear zones), not evenly everywhere
    patch = g.node("ShaderNodeTexNoise", Vector=co, Scale=1.3, Detail=3.0, Roughness=0.55).outputs["Fac"]
    chips = g.math("MULTIPLY", chips, g.ramp(patch, 0.5, 0.66))
    bev = g.node("ShaderNodeBevel", Radius=spec.get("edge_radius", min(0.006, tile * 0.03)), _samples=8)
    geo = g.node("ShaderNodeNewGeometry")
    dot = g.node("ShaderNodeVectorMath", _operation="DOT_PRODUCT")
    g.set(dot.inputs[0], bev.outputs[0])
    g.set(dot.inputs[1], geo.outputs["Normal"])
    edge = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, dot.outputs["Value"]), 30.0, clamp=True)
    edge_break = g.node("ShaderNodeTexNoise", Vector=co, Scale=9.0, Detail=8.0, Roughness=0.7).outputs["Fac"]
    edge = g.ramp(g.math("MULTIPLY", edge, edge_break), 0.25, 0.45)
    scr = g.ramp(_lum(g, _img(g, "scratches", "color", _uv(g, tile * 0.7, (7.7, 2.9)), True).outputs["Color"]), 0.09, 0.3)
    worn = g.math("MAXIMUM", g.math("MULTIPLY", chips, wear * 1.1), g.math("MULTIPLY", edge, min(1.0, wear * 1.5)))
    if kind == "plastic":
        worn = g.math("MULTIPLY", worn, 0.0)
    worn = g.math("MINIMUM", worn, 1.0)
    col = g.mix(worn, base, bare)
    col = g.mix(g.math("MULTIPLY", scr, wear * 0.55, clamp=True), col, (0.5, 0.5, 0.52, 1))

    # grime: streaks down the faces + dirt in crevices
    grime_c = _img(g, "grime", "color", _uv(g, tile * 3.2, (5.1, 3.3))).outputs["Color"]
    gpatch = g.node("ShaderNodeTexNoise", Vector=co, Scale=0.9, Detail=2.0, Roughness=0.5).outputs["Fac"]
    col = _grime(g, col, grime_c, g.math("MULTIPLY", g.ramp(gpatch, 0.42, 0.7), dirt * 0.75))
    ao = g.node("ShaderNodeAmbientOcclusion", Distance=tile * 0.12, _samples=8)
    cav = g.ramp(g.math("SUBTRACT", 1.0, ao.outputs["AO"]), 0.15, 0.7)
    col = g.mix(g.math("MULTIPLY", cav, dirt * 0.9), col, (0.05, 0.04, 0.03, 1))
    g.set(bsdf.inputs["Base Color"], col)

    g.set(bsdf.inputs["Metallic"], worn)
    r = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, det), 2.0))
    r = g.mixf(worn, r, 0.32)
    r = g.mixf(g.math("MULTIPLY", scr, wear * 0.8, clamp=True), r, 0.22)
    r = g.mixf(g.math("MULTIPLY", cav, dirt), r, 0.85)
    g.set(bsdf.inputs["Roughness"], r)
    # clear coat: the glossy lacquer layer that makes painted surfaces read as finished objects
    bsdf.inputs["Coat Weight"].default_value = 0.25 if kind == "plastic" else 0.35
    bsdf.inputs["Coat Roughness"].default_value = 0.12

    nm = g.node("ShaderNodeNormalMap", Color=_img(g, tid, "normal", co, True).outputs["Color"], Strength=0.6)
    chip_step = g.node("ShaderNodeBump", Strength=0.35, Distance=0.0015, Height=g.math("SUBTRACT", 1.0, worn),
                       Normal=nm.outputs[0])
    g.set(bsdf.inputs["Normal"], chip_step.outputs[0])


def _mul(g, color, factor_sock):
    nd = g.node("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    nd.inputs["Factor"].default_value = 1.0
    g.set(nd.inputs["A"], color)
    comb = g.node("ShaderNodeCombineColor")
    for k in ("Red", "Green", "Blue"):
        g.set(comb.inputs[k], factor_sock)
    g.set(nd.inputs["B"], comb.outputs[0])
    return nd.outputs["Result"]


def _grime(g, col, grime_c, amount):
    """Multiply the grime photo in, normalised so its clean background leaves the colour unchanged."""
    p = META["grime"]["p95"]
    m = ((p + 0.055) / 1.055) ** 2.4          # the grime photo is read as sRGB colour, so compare in linear
    scaled = g.node("ShaderNodeMix", _data_type="RGBA", _blend_type="DIVIDE")
    scaled.inputs["Factor"].default_value = 1.0
    g.set(scaled.inputs["A"], grime_c)
    scaled.inputs["B"].default_value = (m, m, m, 1)
    clamp = g.node("ShaderNodeMix", _data_type="RGBA", _blend_type="DARKEN")
    clamp.inputs["Factor"].default_value = 1.0
    g.set(clamp.inputs["A"], scaled.outputs["Result"])
    clamp.inputs["B"].default_value = (1, 1, 1, 1)
    mult = g.node("ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    if isinstance(amount, (int, float)):
        mult.inputs["Factor"].default_value = min(1.0, amount * 1.3)
    else:
        g.set(mult.inputs["Factor"], amount)
    g.set(mult.inputs["A"], col)
    g.set(mult.inputs["B"], clamp.outputs["Result"])
    return mult.outputs["Result"]
