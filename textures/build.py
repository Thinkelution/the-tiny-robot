"""Turn the raw generated images into seamless PBR texture maps.

  python textures/build.py

For each picked image: crop the outer border (generators like to draw plate edges), flatten the photo's lighting
(divide out a large blur), make it tile (blend with a half-offset copy, variance-preserving), then write
lib/<id>/color.png (sRGB), height.png (16-bit, high-passed luminance) and normal.png (OpenGL convention, as
Blender expects). Also writes lib/sheet.png: every map tiled 2x2, so seams would show.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
RAW, LIB = HERE / "raw", HERE / "lib"
SIZE = 1024
# picked variant, normal strength, high-pass sigma for height (px)
PICKS = {
    "paint_worn": ("paint_worn__v2_1", 2.0, 6),
    "paint_clean": ("paint_clean__2", 1.0, 6),
    "metal_brushed": ("metal_brushed__0", 1.5, 3),
    "brass_old": ("brass_old__1", 1.5, 6),
    "rubber": ("rubber__0", 2.5, 4),
    "grime": ("grime__0", 0.0, 0),
    "scratches": ("scratches__1", 0.0, 0),
    "glass_smudge": ("glass_smudge__0", 0.0, 0),
    "chips": ("chips__v2_1", 0.0, 0),
    "concrete": ("concrete__2", 2.0, 6),
    "asphalt": ("asphalt__0", 2.5, 4),
    "corrugated": ("corrugated__2", 3.0, 10),
    "metal_plate": ("metal_plate__1", 3.0, 8),
    "leaves": ("leaves__1", 2.5, 5),
    "bark": ("bark__0", 3.0, 6),
}


def load(name):
    im = Image.open(RAW / f"{name}.png").convert("RGB")
    w, h = im.size
    m = int(min(w, h) * 0.07)
    im = im.crop((m, m, w - m, h - m)).resize((SIZE, SIZE), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def flatten(a, sigma=90):
    """Remove slow lighting gradients but keep the average colour."""
    low = np.stack([gaussian_filter(a[..., c], sigma, mode="reflect") for c in range(3)], -1)
    mean = a.reshape(-1, 3).mean(0)
    return np.clip(a / np.maximum(low, 1e-3) * mean, 0, 1)


def tileable(a):
    h, w = a.shape[:2]
    b = np.roll(a, (h // 2, w // 2), (0, 1))
    y = np.sin(np.pi * (np.arange(h) + 0.5) / h)[:, None]
    x = np.sin(np.pi * (np.arange(w) + 0.5) / w)[None, :]
    wgt = np.clip((x * y) ** 0.6 * 1.6, 0, 1)
    if a.ndim == 3:
        wgt = wgt[..., None]
    mean = a.mean(axis=(0, 1))
    mix = a * wgt + b * (1 - wgt)
    norm = np.sqrt(wgt ** 2 + (1 - wgt) ** 2)
    return np.clip(mean + (mix - mean) / norm, 0, 1)


def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def height_from(a, sigma):
    l = lum(a)
    hp = l - gaussian_filter(l, sigma * 4, mode="wrap")
    hp = gaussian_filter(hp, 0.6, mode="wrap")
    lo, hi = np.percentile(hp, (1, 99))
    return np.clip((hp - lo) / max(hi - lo, 1e-6), 0, 1)


def normal_from(hgt, strength):
    dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5 * strength
    dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5 * strength
    n = np.stack([-dx, dy, np.ones_like(hgt)], -1)   # OpenGL: +Y up (image rows go down, so flip dy)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save8(a, p):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(p)


def save16(a, p):
    Image.fromarray((np.clip(a, 0, 1) * 65535 + 0.5).astype(np.uint16)).save(p)


def main():
    tiles = []
    meta = {}
    for tid, (src, strength, sigma) in PICKS.items():
        if not (RAW / f"{src}.png").exists():
            print("missing", src)
            continue
        out = LIB / tid
        out.mkdir(parents=True, exist_ok=True)
        col = tileable(flatten(load(src)))
        save8(col, out / "color.png")
        row = [col]
        if sigma:
            hgt = height_from(col, sigma)
            save16(hgt, out / "height.png")
            nrm = normal_from(hgt, strength)
            save8(nrm, out / "normal.png")
            row += [np.repeat(hgt[..., None], 3, -1), nrm]
        tiles.append((tid, row))
        l = lum(col)
        meta[tid] = {"mean_lum": round(float(l.mean()), 4), "p95": round(float(np.percentile(l, 95)), 4),
                     "p5": round(float(np.percentile(l, 5)), 4)}
        print("built", tid)
    import json
    (LIB / "meta.json").write_text(json.dumps(meta, indent=1))
    # 2x2 tiled preview of every map, so seams would be visible
    t = 220
    sheet = Image.new("RGB", (t * 2 * 3, t * 2 * len(tiles)), "white")
    for r, (_, row) in enumerate(tiles):
        for c, a in enumerate(row):
            im = Image.fromarray((a * 255).astype(np.uint8)).resize((t, t))
            for dy in (0, t):
                for dx in (0, t):
                    sheet.paste(im, (c * 2 * t + dx, r * 2 * t + dy))
    sheet.save(LIB / "sheet.png")


if __name__ == "__main__":
    main()
