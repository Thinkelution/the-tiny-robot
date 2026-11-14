"""Cast stage: bible characters -> boxy robot specs -> Blender studio renders -> Claude checks them -> fixes.

  python agent/cast.py <film-folder> [specs|render|check|all] [--only id,id] [--rounds N] [--samples N]

Writes <film>/cast/<id>.json, renders to <film>/cast/review/, and the check notes to <film>/cast/<id>.check.json.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import ask, image_block  # noqa: E402

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
ROOT = Path(__file__).resolve().parent.parent
S, N, I = {"type": "string"}, {"type": "number"}, {"type": "integer"}


def arr(x):
    return {"type": "array", "items": x}


def obj(**p):
    return {"type": "object", "properties": p}


def enum(*v):
    return {"type": "string", "enum": list(v)}


V3 = arr(N)
ROBOT = obj(
    id=S, name=S, height_m=N, locomotion=enum("walk", "hop", "wheels", "treads", "hover"),
    materials=arr(obj(id=S, kind=enum("painted_metal", "bare_metal", "rubber", "plastic", "glass", "emissive"),
                      color=S, roughness=N, metallic=N, wear=N, dirt=N,
                      pattern=enum("none", "stripes", "hazard"), pattern_color=S, emission=N)),
    parts=arr(obj(name=S, role=enum("body", "head", "arm_l", "arm_r", "forearm_l", "forearm_r", "hand_l", "hand_r",
                                    "leg_l", "leg_r", "foot_l", "foot_r", "wheel", "tread", "antenna", "tail",
                                    "tool", "extra"),
                  parent=S, shape=enum("box", "slab", "rounded_box", "cylinder_x", "cylinder_y", "cylinder_z"),
                  size=V3, pivot=V3, offset=V3, rotate=V3, material=S, bevel=N)),
    face=obj(part=S, screen=arr(N), at=arr(N), eye_color=S, eyes=I, eye_size=arr(N), eye_gap=N, glow=S),
    details=arr(obj(part=S, kind=enum("bolts", "vent", "panel", "light", "badge", "antenna"),
                    side=enum("front", "back", "left", "right", "top"), u=N, v=N, w=N, h=N, count=I,
                    length=N, color=S, material=S)),
    design_notes=S,
)
CHECK = obj(matches=enum("yes", "mostly", "no"), problems=arr(S), studio_quality_notes=arr(S), revised=ROBOT)

SYSTEM = """You are the lead character modeller at an animation studio. Your models are built by code from a JSON
parts list, so you design with boxes and simple cylinders only, and you think precisely in metres.

BUILDER CONVENTIONS
- Z is up. The robot faces -Y (its front is the -Y side). The robot's LEFT is +X, its RIGHT is -X.
- With the robot standing at the origin, its lowest point touches z = 0 and its top is at about height_m.
- Each part is a box of `size` [x, y, z] (full widths, metres). Shapes: box, slab (thin box), rounded_box (heavily
  rounded), cylinder_x / cylinder_y / cylinder_z (axis along that direction; wheels are cylinder_x).
- `parent` is another part's name or "root". `pivot` is the part's JOINT position relative to the parent's joint
  (the root joint is the origin on the ground). `offset` is where the box centre sits relative to its own joint.
  Example: an arm hangs from a shoulder joint, so pivot = shoulder position, offset = [0, 0, -half the arm length].
  Feet: pivot at the ankle, box offset down so its bottom reaches z = 0.
- `rotate` is a static rotation in degrees [x, y, z] of the box around its centre (usually [0, 0, 0]).
- `bevel` is the edge rounding in metres (0.004-0.04 typical; it makes edges catch light, so never 0 on main parts).
- Roles drive the animation, so use them exactly: body, head, arm_l/arm_r (upper arm from the shoulder),
  forearm_l/forearm_r (child of the arm, pivot at the elbow), hand_l/hand_r, leg_l/leg_r (from the hip),
  foot_l/foot_r, wheel (each wheel its own part, pivot at the axle), tread, antenna, tail, tool, extra.
  Walkers and hoppers need foot_l and foot_r. Floating hands or feet are allowed (parent them to the body or head
  with a gap, no arm or leg between).
- `face`: `part` is the part whose FRONT side carries a dark glass screen of size [w, h], centred at [x, z] offset
  `at` on that side. `eyes` is 1 or 2 glowing eye shapes of `eye_size` [w, h], `eye_gap` apart (centre to
  centre). The eyes animate (blink, happy, sad, angry, wide), so they must be big and readable.
- `details` add studio detail on a part's side: bolts (4 corner bolts), vent (`count` slats), panel (raised plate,
  `w`/`h` as fractions of the side, `u`/`v` position from -1 to 1), light (small glowing block, `color`), badge
  (plate in `material`), antenna (`length` metres, `color` tip). Unused numeric fields = 0, unused strings = "".
- materials: `kind` painted_metal (paint that wears off the edges to bare metal), bare_metal, rubber, plastic, glass,
  emissive. `color` is hex. wear and dirt 0-1 (old robots 0.5-0.8, shiny new ones 0.05-0.2). Roughness 0.2-0.9.
  Use 2-5 materials per robot. Prefix material ids with the robot id so robots never share materials.
- Proportion and silhouette first: each robot must read instantly in silhouette and at a distance, and its shapes
  must say something about its logic. Add enough secondary detail (panels, bolts, vents, lights, trims, a badge)
  that close-ups hold up, but keep the primary shapes simple and bold. Aim for 12-35 parts."""


def _clean(spec):
    """Drop the zero/empty placeholder fields strict outputs force into details."""
    for d in spec.get("details", []):
        for k in ("u", "v", "w", "h", "count", "length", "color", "material"):
            if d.get(k) in (0, "", None) and k not in ("u", "v"):
                d.pop(k, None)
    return spec


class Cast:
    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        self.out = self.dir / "cast"
        (self.out / "review").mkdir(parents=True, exist_ok=True)
        self.bible = json.loads((self.dir / "bible.json").read_text(encoding="utf-8"))
        self.log = self.dir / "llm-log.jsonl"
        self.chars = {c["id"]: c for c in self.bible["characters"]}

    def spec(self, cid, force=False):
        p = self.out / f"{cid}.json"
        if p.exists() and not force:
            return json.loads(p.read_text(encoding="utf-8"))
        c = self.chars[cid]
        heights = {k: v["height_m"] for k, v in self.chars.items()}
        extra = ""
        if cid == "tiny":
            extra = ("\nThe owner's design for this robot is fixed: it is ONLY a head with two small hands and two "
                     "small feet. No body, no arms, no legs: the hands and feet float near the head (parent them to "
                     "the head with small gaps) like a cartoon character. It must be adorable, readable and old.")
        prompt = f"""Film: {self.bible['title']} (world: {self.bible['world']['name']}).
World look: {self.bible['world']['look']}

Design this robot as a parts list:
{json.dumps(c, indent=1, ensure_ascii=False)}

Heights of the whole cast in metres, for scale: {json.dumps(heights)}{extra}

Write `design_notes` (3-5 sentences: silhouette idea, how the shapes express its logic, colour story)."""
        spec = ask(prompt, system=SYSTEM, schema=ROBOT, effort="high", log=self.log, label=f"cast {cid}")
        spec["id"] = cid
        p.write_text(json.dumps(_clean(spec), indent=2, ensure_ascii=False), encoding="utf-8")
        return spec

    def render(self, ids, samples=96, only=""):
        files = [str(self.out / f"{i}.json") for i in ids]
        cmd = [BLENDER, "-b", "--factory-startup", "-P", str(ROOT / "blender" / "turnaround.py"), "--",
               str(self.out / "review"), *files, "--samples", str(samples)]
        if only:
            cmd += ["--only", only]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        errs = [l for l in r.stdout.splitlines() + r.stderr.splitlines() if "Traceback" in l]
        if r.returncode != 0 or errs:
            print("\n".join((r.stdout + r.stderr).splitlines()[-30:]))
            raise SystemExit(f"Blender failed for {ids}")

    def check(self, cid):
        spec = self.spec(cid)
        rev = self.out / "review"
        imgs = [image_block(rev / f"{cid}_turn.png")]
        if (rev / f"{cid}_faces.png").exists():
            imgs.append(image_block(rev / f"{cid}_faces.png"))
        prompt = imgs + [{"type": "text", "text": f"""These are studio renders of the robot built from this spec
(first image: front, three-quarter, side, back; second image: face expressions neutral, blink, happy, sad, angry, wide).

<character>
{json.dumps(self.chars[cid], indent=1, ensure_ascii=False)}
</character>

<spec>
{json.dumps(spec, indent=1, ensure_ascii=False)}
</spec>

Check the model like a lead modeller in dailies:
1. Does it match the character description and read clearly in silhouette? Parts floating where they should be
   attached, parts intersecting badly, wrong proportions, things below the floor, unreadable eyes, a face that is
   hidden or too small.
2. Studio quality: bevels, material contrast, detail density for close-ups, colour harmony.
List the problems, then return the full `revised` spec with every fix applied (same id, same conventions). If it is
already right, return the spec unchanged."""}]
        res = ask(prompt, system=SYSTEM, schema=CHECK, effort="high", log=self.log, label=f"check {cid}")
        (self.out / f"{cid}.check.json").write_text(json.dumps(
            {k: v for k, v in res.items() if k != "revised"}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {cid}: matches={res['matches']}; {len(res['problems'])} problems")
        return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {sys.argv[i][2:]: sys.argv[i + 1] for i in range(len(sys.argv) - 1) if sys.argv[i].startswith("--")}
    cast = Cast(args[0])
    step = args[1] if len(args) > 1 else "all"
    ids = opt["only"].split(",") if "only" in opt else list(cast.chars)
    samples = int(opt.get("samples", 96))
    if step in ("specs", "all"):
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda i: cast.spec(i, force="force" in opt), ids))
    if step == "render":
        for i in ids:
            cast.render([i], samples)
    if step in ("check", "all"):
        for rnd in range(int(opt.get("rounds", 2))):
            for i in ids:
                cast.render([i], samples)
            with ThreadPoolExecutor(4) as pool:
                results = list(pool.map(cast.check, ids))
            redo = []
            for i, res in zip(ids, results):
                if res["matches"] != "yes" or res["problems"]:
                    spec = _clean(res["revised"])
                    spec["id"] = i
                    (cast.out / f"{i}.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
                    redo.append(i)
            print(f"  round {rnd + 1}: revised {redo}")
            if not redo:
                break
            ids = redo
        for i in list(cast.chars):
            cast.render([i], samples)
        cast.render(list(cast.chars), samples, only="lineup")


if __name__ == "__main__":
    main()
