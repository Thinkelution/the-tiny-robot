"""Top-down plan of the film's city, drawn from films/<film>/world/city.json, for review before any set is built.

  python agent/citymap.py films/the-tiny-robot        -> films/the-tiny-robot/world/map.png
"""
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
COLORS = {
    "old_grove": "#4f9a5a", "rooftop_nursery": "#8cc96b", "pipeworks": "#4f7fa8", "main_square": "#c9a24a",
    "count_house": "#d08a3a", "foundry": "#c75a3a", "fast_lane_works": "#e3b51e", "junk_stacks": "#9a6e4f",
}
ROUTE_COLORS = {"tiny_home_to_grove": "#f4efe6", "grove_boulevard": "#e8e2d6", "water_main_grove": "#5fc3ff",
                "water_main_nursery": "#5fc3ff", "fast_lane_curve": "#ffcc33"}


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def main(film):
    film = Path(film)
    city = json.loads((film / "world" / "city.json").read_text(encoding="utf-8"))
    x0, x1, y0, y1 = -205, 175, -175, 95
    S = 6.5
    W, H = int((x1 - x0) * S), int((y1 - y0) * S)
    img = Image.new("RGB", (W, H + 150), "#1b2027")
    d = ImageDraw.Draw(img, "RGBA")

    def P(x, y):
        return ((x - x0) * S, (y1 - y) * S)

    def rect(cx, cy, w, h):
        a, b = P(cx - w / 2, cy + h / 2)
        c, e = P(cx + w / 2, cy - h / 2)
        return [a, b, c, e]

    locs = city["locations"]
    keep_out = [(l["centre"][0], l["centre"][1], l["size"][0] + 14, l["size"][1] + 14) for l in locs]
    keep_out.append((64, 0, 64, 14))                       # Grove Boulevard

    def clear(cx, cy, w, h):
        for (lx, ly, lw, lh) in keep_out:
            if abs(cx - lx) < (w + lw) / 2 and abs(cy - ly) < (h + lh) / 2:
                return False
        return True

    # city blocks on a 30 m street grid, filled with tower footprints
    rnd = random.Random(3)
    d.rectangle([0, 0, W, H], fill="#2a3038")
    for gx in range(x0, x1, 30):
        for gy in range(y0, y1, 30):
            cx, cy = gx + 15, gy + 15
            if not clear(cx, cy, 30, 30):
                continue
            d.rectangle(rect(cx, cy, 30, 30), fill="#232830")
            for (ox, oy) in ((-6, -6), (6, -6), (-6, 6), (6, 6)):
                if rnd.random() < 0.85:
                    w, h = rnd.uniform(8, 11), rnd.uniform(8, 11)
                    shade = rnd.randint(70, 105)
                    d.rectangle(rect(cx + ox, cy + oy, w, h), fill=(shade, shade + 4, shade + 10))
    # Grove Boulevard
    d.rectangle(rect(64, 0, 64, 12), fill="#3a4049")

    title = font("LilitaOne-Regular.ttf", 30)
    small = font("Fredoka-Regular.ttf" if (FONTS / "Fredoka-Regular.ttf").exists() else "Poppins-Medium.ttf", 17)
    tiny = font("Poppins-Medium.ttf", 14)
    for l in locs:
        cx, cy = l["centre"]
        w, h = l["size"]
        col = COLORS.get(l["id"], "#888888")
        r = rect(cx, cy, w, h)
        fill = col + ("cc" if l["kind"] == "exterior" else "55")
        d.rectangle(r, fill=fill, outline=col, width=4)
        if l["kind"] == "interior":
            d.line([r[0], r[1], r[2], r[3]], fill=col, width=2)
            d.line([r[0], r[3], r[2], r[1]], fill=col, width=2)
        if l["id"] == "old_grove":
            for k in range(60):
                tx, ty = cx + rnd.uniform(-w / 2 + 4, w / 2 - 4), cy + rnd.uniform(-h / 2 + 4, h / 2 - 4)
                if (tx - cx) ** 2 + (ty - cy) ** 2 < 49:
                    continue
                rr = rnd.uniform(1.6, 3.2) * S
                px, py = P(tx, ty)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=rnd.choice(["#2f7a3d", "#3d8f47", "#5aa85a", "#6dbb5d"]))
            px, py = P(cx, cy)
            d.ellipse([px - 22 * S, py - 22 * S, px + 22 * S, py + 22 * S], outline="#d9c99a", width=3)
            d.ellipse([px - 7, py - 7, px + 7, py + 7], fill="#b8f08a")
    # routes
    for rt in city["routes"]:
        pts = [P(*p) for p in rt["points"]]
        col = ROUTE_COLORS.get(rt["id"], "#ffffff")
        for (a, b) in zip(pts, pts[1:]):
            n = max(1, int(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 / 14))
            for k in range(0, n, 2):
                s0, s1 = k / n, min(1, (k + 1) / n)
                d.line([(a[0] + (b[0] - a[0]) * s0, a[1] + (b[1] - a[1]) * s0),
                        (a[0] + (b[0] - a[0]) * s1, a[1] + (b[1] - a[1]) * s1)], fill=col, width=4)
        lx, ly = pts[len(pts) // 2]
        d.text((lx + 8, ly - 22), rt["label"], font=tiny, fill=col)
    # labels
    for l in locs:
        cx, cy = l["centre"]
        w, h = l["size"]
        px, py = P(cx - w / 2, cy + h / 2)
        px = max(px, 12)
        name = l["id"].replace("_", " ").title()
        label = f"{name}{'  (interior set)' if l['kind'] == 'interior' else ''}"
        sub = " ".join(l["scenes"])
        tw = max(d.textlength(label, font=small), d.textlength(sub, font=tiny)) + 16
        ly = py - 50 if py > 60 else py + h * S + 6
        d.rounded_rectangle([px, ly, px + tw, ly + 46], 8, fill=(15, 18, 24, 215))
        d.text((px + 8, ly + 4), label, font=small, fill=COLORS.get(l["id"], "#fff"))
        d.text((px + 8, ly + 26), sub, font=tiny, fill="#c9d1da")
    # compass + scale bar
    d.text((W - 70, 20), "N", font=title, fill="#f4efe6")
    d.polygon([(W - 58, 60), (W - 66, 84), (W - 50, 84)], fill="#f4efe6")
    sx, sy = 30, H - 40
    d.line([(sx, sy), (sx + 50 * S, sy)], fill="#f4efe6", width=4)
    d.text((sx, sy - 26), "50 m", font=tiny, fill="#f4efe6")
    # footer
    d.text((30, H + 18), "Gridhaven: city plan", font=title, fill="#f4efe6")
    d.text((30, H + 66), "Solid = outdoor set built in the shared city.   Crossed = interior set (its outside is in the city, its inside is built separately).",
           font=small, fill="#c9d1da")
    d.text((30, H + 96), "Grey squares = background towers.   Dashed lines = routes the story uses.", font=small, fill="#c9d1da")
    out = film / "world" / "map.png"
    img.save(out)
    print(out, img.size)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "films/the-tiny-robot")
