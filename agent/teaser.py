"""Build the teaser reel from films/<film>/teaser/teaser.json.

  python agent/teaser.py <film-folder> [render|music|post|all] [--only shot,shot] [--samples N]

render  each shot through blender/teaser.py into teaser/shots/<id>/####.png (skips shots already complete)
music   Eleven Music bed following the sections in teaser.json (ElevenLabs2 key)
post    captions composited on every frame (Pillow), end card, then ffmpeg -> teaser/the-tiny-robot-teaser.mp4
"""
import json
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
KEYS = Path("F:/work/keys.txt")
FONT_NAME = "C:/Windows/Fonts/bahnschrift.ttf"
FONT_TEXT = "C:/Windows/Fonts/seguisb.ttf" if Path("C:/Windows/Fonts/seguisb.ttf").exists() else "C:/Windows/Fonts/segoeuib.ttf"
GLOW, AMBER, WHITE, SOFT = (156, 255, 176), (242, 183, 5), (255, 255, 255), (214, 220, 228)


def bahn(size, style="Bold"):
    f = ImageFont.truetype(FONT_NAME, size)
    try:
        f.set_variation_by_name(style)
    except Exception:
        pass
    return f


class Teaser:
    def __init__(self, film):
        self.film = Path(film).resolve()
        self.dir = self.film / "teaser"
        self.cfg = json.loads((self.dir / "teaser.json").read_text(encoding="utf-8"))
        self.W, self.H = self.cfg["size"]

    # ------------------------------------------------------------ render
    def render(self, only=None, samples=40):
        for s in self.cfg["shots"]:
            if s["mode"] == "card" or (only and s["id"] not in only):
                continue
            out = self.dir / "shots" / s["id"]
            if out.exists() and len(list(out.glob("[0-9]*.png"))) >= s["frames"]:
                print("  done already:", s["id"])
                continue
            robots = s.get("robots") or [s["robot"]]
            specs = [str(self.film / "cast" / f"{r}.json") for r in robots]
            cmd = [BLENDER, "-b", "--factory-startup", "-P", str(ROOT / "blender" / "teaser.py"), "--",
                   str(out), s["mode"], *specs, "--frames", str(s["frames"]), "--samples", str(samples),
                   "--res", f"{self.W}x{self.H}"]
            print("  rendering", s["id"], flush=True)
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0 or "Traceback" in r.stdout + r.stderr:
                print((r.stdout + r.stderr)[-3000:])
                sys.exit(f"render failed: {s['id']}")

    # ------------------------------------------------------------ music
    def music(self):
        total = sum(s["frames"] for s in self.cfg["shots"]) / self.cfg["fps"]
        key = next(l.split()[1] for l in KEYS.read_text(encoding="utf-8").splitlines()
                   if l.split() and l.split()[0].rstrip(":").lower() == "elevenlabs2")
        chunks, start = [], 0.0
        base = ["instrumental", "background score for an animated film teaser", "no vocals"]
        for name, until, styles in self.cfg["music"]:
            end = until if until is not None else total
            chunks.append({"text": f"[{name}]", "duration_ms": int(round((end - start) * 1000)),
                           "positive_styles": styles + base, "negative_styles": ["vocals", "lyrics", "heavy drums"],
                           "context_adherence": "high"})
            start = end
        body = {"composition_plan": {"chunks": chunks}, "model_id": "music_v2_5"}
        req = urllib.request.Request("https://api.elevenlabs.io/v1/music", data=json.dumps(body).encode(),
                                     method="POST", headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                (self.dir / "music.mp3").write_bytes(r.read())
        except urllib.error.HTTPError as e:
            sys.exit(f"Eleven Music failed ({e.code}): {e.read().decode('utf-8', 'replace')[:500]}")
        print(f"  music.mp3 ({total:.1f} s)")

    # ------------------------------------------------------------ captions
    def _shadowed(self, img, xy_text_font_fill, anchor="ma"):
        """Draw text with a soft dark shadow so it reads on any frame."""
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        for (x, y), text, font, fill, alpha in xy_text_font_fill:
            sd.multiline_text((x, y + 4), text, font=font, fill=(0, 0, 0, int(200 * alpha)), anchor=anchor,
                              align="center", spacing=int(font.size * 0.22))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        img.alpha_composite(shadow)
        d = ImageDraw.Draw(img)
        for (x, y), text, font, fill, alpha in xy_text_font_fill:
            d.multiline_text((x, y), text, font=font, fill=fill + (int(255 * alpha),), anchor=anchor, align="center",
                             spacing=int(font.size * 0.22))

    def _fade(self, f, a, b, n=8):
        if f < a or f >= b:
            return 0.0
        return min(1.0, (f - a + 1) / n, (b - f) / n)

    def caption_layers(self, shot, f):
        W, H = self.W, self.H
        items = []
        top = int(H * 0.115)
        if shot["mode"] == "intro":
            al = self._fade(f, 14, shot["frames"], 8)
            if al > 0:
                items.append(((W // 2, top), shot["name"], bahn(104), WHITE, al))
                logic = "\n".join(textwrap.wrap(f"“{shot['logic']}”", 26))
                items.append(((W // 2, top + 150), logic, ImageFont.truetype(FONT_TEXT, 54), SOFT, al))
        for c in shot.get("captions", []):
            al = self._fade(f, c["from"], c["to"], 10)
            if al <= 0:
                continue
            k = c["kind"]
            if k == "question":
                items.append(((W // 2, top), "\n".join(textwrap.wrap(c["text"], 24)), ImageFont.truetype(FONT_TEXT, 66),
                              WHITE, al))
            elif k == "sub":
                items.append(((W // 2, top + 330), c["text"], bahn(92), GLOW, al))
            elif k == "big":
                items.append(((W // 2, int(H * 0.2)), c["text"], bahn(150), AMBER, al))
            elif k == "end":
                items.append(((W // 2, int(H * 0.36)), "\n".join(textwrap.wrap(c["text"], 22)),
                              ImageFont.truetype(FONT_TEXT, 70), WHITE, al))
            elif k == "credit":
                items.append(((W // 2, int(H * 0.62)), c["text"].replace(" · ", "\n"), bahn(44, "SemiBold"),
                              SOFT, al))
        return items

    # ------------------------------------------------------------ post
    def post(self):
        out = self.dir / "frames"
        out.mkdir(exist_ok=True)
        for old in out.glob("*.png"):
            old.unlink()
        n = 0
        last = None
        for s in self.cfg["shots"]:
            for f in range(s["frames"]):
                if s["mode"] == "card":
                    if f == 0:
                        base = last.filter(ImageFilter.GaussianBlur(18))
                        dark = Image.new("RGBA", base.size, (8, 10, 16, 170))
                        base = Image.alpha_composite(base, dark)
                    img = base.copy()
                else:
                    img = Image.open(self.dir / "shots" / s["id"] / f"{f + 1:04d}.png").convert("RGBA")
                    if img.size != (self.W, self.H):
                        img = img.resize((self.W, self.H), Image.LANCZOS)
                    last = img
                if s["id"] == "hook" or s["mode"] == "card":
                    pass
                items = self.caption_layers(s, f)
                if items:
                    img = img.copy()
                    self._shadowed(img, items)
                n += 1
                img.convert("RGB").save(out / f"{n:05d}.png", compress_level=1)
            print("  post:", s["id"], flush=True)
        video = self.dir / "the-tiny-robot-teaser.mp4"
        cmd = ["ffmpeg", "-y", "-framerate", str(self.cfg["fps"]), "-i", str(out / "%05d.png")]
        music = self.dir / "music.mp3"
        if music.exists():
            cmd += ["-i", str(music), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={:.2f}:d=1.2".format(
                n / self.cfg["fps"] - 1.2), "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(video)]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  {video.name}: {n} frames, {n / self.cfg['fps']:.1f} s")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {sys.argv[i][2:]: sys.argv[i + 1] for i in range(len(sys.argv) - 1) if sys.argv[i].startswith("--")}
    t = Teaser(args[0])
    step = args[1] if len(args) > 1 else "all"
    only = opt["only"].split(",") if "only" in opt else None
    if step in ("render", "all"):
        t.render(only, int(opt.get("samples", 40)))
    if step in ("music", "all") and not (t.dir / "music.mp3").exists():
        t.music()
    if step in ("post", "all"):
        t.post()


if __name__ == "__main__":
    main()
