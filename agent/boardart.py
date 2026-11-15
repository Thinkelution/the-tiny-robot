"""Pictures for the Big Board screen in Main Square (Pillow), one per beat of the story.

  python agent/boardart.py films/the-tiny-robot   -> films/the-tiny-robot/world/textures/board_*.png

- fastlane: S03, Quota's pitch: a straight road with a bend around a cluster of green cubes, "THE FAST LANE"
- grove_red: S09, the Old Grove with its gauge grates glowing red
- vote: S17, the split vote, green against red
Flat, bold, Gridhaven-boxy: these are screens inside the film, so they stay simple and readable from far away.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets" / "fonts" / "LilitaOne-Regular.ttf"
W, H = 1600, 900
BG = (14, 22, 40)


def base():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(0, H, 6):                       # faint scanlines
        d.line([(0, y), (W, y)], fill=(18, 28, 50))
    return img, d


def glow(img):
    g = img.filter(ImageFilter.GaussianBlur(14))
    return Image.blend(img, g, 0.25)


def cubes(d, cx, cy, s, colour, n=7):
    import random
    rnd = random.Random(4)
    for _ in range(n):
        x, y = cx + rnd.uniform(-1.6, 1.6) * s, cy + rnd.uniform(-1.0, 1.0) * s
        k = s * rnd.uniform(0.7, 1.1)
        d.rounded_rectangle([x - k / 2, y - k / 2, x + k / 2, y + k / 2], radius=k * 0.25, fill=colour)


def fastlane(out):
    img, d = base()
    f = ImageFont.truetype(str(FONT), 130)
    d.text((W / 2, 120), "THE FAST LANE", font=f, anchor="mm", fill=(255, 196, 40))
    # the road: straight from the left, bending round the green cubes on the right
    y = 560
    grey = (200, 205, 214)
    d.line([(80, y), (960, y)], fill=grey, width=70)
    d.arc([925, y - 250, 1435, y + 250], start=180, end=360, fill=grey, width=70)   # up and over the cubes
    d.line([(1400, y), (1560, y)], fill=grey, width=70)
    for x in range(120, 940, 90):
        d.line([(x, y), (x + 45, y)], fill=(255, 196, 40), width=10)
    cubes(d, 1180, y + 40, 60, (90, 200, 110))
    f2 = ImageFont.truetype(str(FONT), 60)
    d.text((420, 720), "FASTER EVERY DAY", font=f2, anchor="mm", fill=(220, 228, 240))
    glow(img).save(out)


def grove_red(out):
    img, d = base()
    f = ImageFont.truetype(str(FONT), 110)
    d.text((W / 2, 110), "THE OLD GROVE", font=f, anchor="mm", fill=(240, 236, 226))
    # drooping brown trees and a row of red gauges
    import random
    rnd = random.Random(7)
    for k in range(7):
        x = 220 + k * 195
        d.rectangle([x - 14, 470, x + 14, 700], fill=(120, 86, 60))
        for _ in range(4):
            cx, cy = x + rnd.uniform(-70, 70), 430 + rnd.uniform(-40, 50)
            s = rnd.uniform(60, 90)
            d.rounded_rectangle([cx - s / 2, cy - s / 2 + 30, cx + s / 2, cy + s / 2 + 30], radius=16,
                                fill=(150, 112, 62))
    for k in range(6):
        x = 260 + k * 220
        d.rectangle([x - 34, 770, x + 34, 810], fill=(60, 64, 72))
        d.ellipse([x - 24, 730, x + 24, 778], fill=(255, 40, 30))
    glow(img).save(out)


def vote(out):
    img, d = base()
    f = ImageFont.truetype(str(FONT), 120)
    d.text((W / 2, 110), "THE VOTE", font=f, anchor="mm", fill=(240, 236, 226))
    d.rounded_rectangle([140, 300, 760, 760], radius=30, fill=(40, 170, 80))
    d.rounded_rectangle([840, 300, 1460, 760], radius=30, fill=(200, 50, 40))
    f2 = ImageFont.truetype(str(FONT), 220)
    d.text((450, 530), "104", font=f2, anchor="mm", fill=(240, 255, 240))
    d.text((1150, 530), "101", font=f2, anchor="mm", fill=(255, 236, 230))
    glow(img).save(out)


def main(film):
    out = Path(film) / "world" / "textures"
    out.mkdir(parents=True, exist_ok=True)
    fastlane(out / "board_fastlane.png")
    grove_red(out / "board_grove_red.png")
    vote(out / "board_vote.png")
    print("board pictures ->", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "films/the-tiny-robot")
