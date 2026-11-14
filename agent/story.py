"""Script stage: a one-paragraph brief -> bible -> scene outline -> every scene written -> continuity pass -> script.md

  python agent/story.py <film-folder> [bible|outline|scenes|review|md|all] [--force]

The film folder holds brief.md (the owner's words). Every stage writes JSON next to it and is skipped when its
file already exists (use --force to redo one). Claude writes everything; nothing here is hand-authored story.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import ask  # noqa: E402

S = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}


def arr(x):
    return {"type": "array", "items": x}


def obj(**props):
    return {"type": "object", "properties": props}


# ------------------------------------------------------------------ production limits every stage writes within
PRODUCTION = """PRODUCTION LIMITS (this film is made automatically in Blender by code, so the story must fit them):
- Every robot is built from boxes and rectangular blocks: cubes, slabs, bars, rounded-off boxes, simple cylinders
  for wheels and joints at most. No organic curves, no cloth, no hair, no liquids splashing.
- Robots move by: walking on feet, hopping, rolling on wheels, treads, or hovering. Arms are simple rigid segments
  or floating hands. Faces are screens or lit eyes that change shape (happy, sad, surprised, angry, sleepy...).
- Animatable actions: go to a place, turn, look at something, point, wave, nod, shake head, shrug, pick up / carry /
  put down / hand over an object the size of a box or bigger, push or pull crates, press buttons and levers, sit,
  fall over and get up, jump, bump into things, tremble, power down and power up, lights and sounds.
- At most 10 robots on screen at once, and crowds only as background. No fast chaotic fights, no explosions bigger
  than a puff of smoke, no tiny-hand manipulation (threading, writing), no readable text needed to follow the story.
- The world is boxy too: block buildings, rectangular streets, pipes, crates, gantries, screens. Plants and trees are
  stylised (box trunks, cube or slab leaf clusters) but clearly alive: they sway, grow, wilt, bloom.
- Weather and light can change (rain as streaks, fog, night, sunrise, warning lights).
- Language: English. Audience: all ages, worldwide; no country- or culture-specific looks. No graphic harm.
"""

SYSTEM = ("You are the head writer of an animated short-film studio. You write warm, funny, surprising, emotionally "
          "honest stories with clear cause and effect, strong visual storytelling, and dialogue that sounds like "
          "the character speaking it. Show, don't tell. Every scene must change something.\n\n" + PRODUCTION)

# ------------------------------------------------------------------ schemas
CHARACTER = obj(
    id=S, name=S, role=S,
    logic=S,                 # the one programmed rule, quoted as the robot would state it
    logic_in_practice=S,     # how that rule makes it behave, good and bad
    blind_spot=S,            # where the rule goes wrong
    arc=S, personality=S, voice=S, speech_style=S,
    look=S,                  # boxy build: size, shapes, locomotion, colours, wear, signature details
    height_m=N, locomotion=S, colours=arr(S),
    relationships=S,
)
BIBLE = obj(
    title=S, tag=S, logline=S, theme=S, tone=S, runtime_minutes=I,
    world=obj(name=S, description=S, how_logics_work=S, rules=arr(S), history=S, look=S),
    characters=arr(CHARACTER),
    locations=arr(obj(id=S, name=S, description=S, look=S, key_props=arr(S), has_plants=B)),
    motifs=arr(S),
    ending=S,
)
OUTLINE = obj(
    acts=arr(obj(act=I, title=S, summary=S)),
    scenes=arr(obj(id=S, act=I, title=S, location_id=S, time_of_day=S, characters=arr(S),
                   summary=S, purpose=S, est_seconds=I)),
)
BEAT = obj(type={"type": "string", "enum": ["action", "dialogue", "sound"]},
           character=S, parenthetical=S, text=S, est_seconds=N)
SCENE = obj(id=S, title=S, location_id=S, time_of_day=S, characters=arr(S), beats=arr(BEAT), staging_notes=S)
REVIEW = obj(overall=S, issues=arr(obj(scene_id=S, problem=S, fix=S)))


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _save(p, data):
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class Film:
    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        self.log = self.dir / "llm-log.jsonl"
        self.brief = (self.dir / "brief.md").read_text(encoding="utf-8")
        (self.dir / "scenes").mkdir(exist_ok=True)

    # 1 ---------------------------------------------------------------- bible
    def bible(self, force=False):
        out = self.dir / "bible.json"
        if out.exists() and not force:
            return _load(out)
        prompt = f"""Here is the owner's brief for the film:

<brief>
{self.brief}
</brief>

Write the series bible for this film. Keep the owner's title, tag, and the Tiny Robot's base logic word for word.

- World: a world of robots, each programmed with one different logic (one rule). Explain how logics are given,
  what happens when two logics collide, and why an old robot with the Tiny Robot's logic is unusual today.
- Cast: the Tiny Robot plus 6 to 9 other robots, each with ONE clearly different programmed logic that is
  quotable in one sentence (e.g. a rule about efficiency, obedience, winning, order, never stopping, pleasing the
  crowd, keeping everything clean...). Each logic must be good in some situations and harmful in others, so the
  story can test it. At least one robot is an antagonist-by-logic, not evil. Give each a boxy look that fits its
  logic and is easy to tell apart in silhouette, a height in metres (the Tiny Robot is the smallest, about 0.35 m),
  and a voice description.
- 6 to 9 locations, all boxy, and at least two with living plants or trees.
- The tag must matter: the plot should turn on telling the truth when a lie would be easier.
- The Tiny Robot never knowingly harms anyone, and it knows trees and plants are living things, so it will not
  harm them either. Use that in the plot, not just as a fact.
- Runtime: about 30 minutes. A clear ending in `ending`.
- `id` fields are short snake_case."""
        data = ask(prompt, system=SYSTEM, schema=BIBLE, effort="high", log=self.log, label="bible")
        _save(out, data)
        return data

    # 2 ---------------------------------------------------------------- outline
    def outline(self, force=False):
        out = self.dir / "outline.json"
        if out.exists() and not force:
            return _load(out)
        bible = self.bible()
        prompt = f"""<bible>
{json.dumps(bible, indent=1, ensure_ascii=False)}
</bible>

Break this film into a scene outline for a 30-minute runtime (est_seconds over all scenes adds up to 1700-1900).
- Three acts. 24 to 32 scenes. Scene ids S01, S02, ...
- Each scene: one location from the bible (location_id), the characters present (character ids), what happens
  (summary, 3-6 sentences, concrete and visual), and its purpose in the story.
- Give the Tiny Robot a want, a real obstacle, a low point where its logic seems to fail it, and a climax where
  its logic and its truthfulness are what save the day. Every other robot's logic gets tested at least once.
- Vary rhythm: quiet scenes, funny scenes, tense scenes, a few nearly wordless scenes.
- Build in setups and payoffs (motifs from the bible)."""
        data = ask(prompt, system=SYSTEM, schema=OUTLINE, effort="high", log=self.log, label="outline")
        total = sum(s["est_seconds"] for s in data["scenes"])
        print(f"  outline: {len(data['scenes'])} scenes, {total / 60:.1f} min")
        _save(out, data)
        return data

    # 3 ---------------------------------------------------------------- scenes
    def scene(self, sid, notes="", force=False):
        out = self.dir / "scenes" / f"{sid}.json"
        if out.exists() and not force:
            return _load(out)
        bible, outline = self.bible(), self.outline()
        scenes = outline["scenes"]
        i = next(k for k, s in enumerate(scenes) if s["id"] == sid)
        me = scenes[i]
        prompt = f"""<bible>
{json.dumps(bible, indent=1, ensure_ascii=False)}
</bible>

<outline>
{json.dumps(outline, indent=1, ensure_ascii=False)}
</outline>

Write scene {sid} "{me['title']}" in full, as beats an animator can stage directly.
Target length: about {me['est_seconds']} seconds.
- `action` beats: what we SEE, in present tense, specific about who does what, where they move, what they look
  at, what their eye-screens show. One beat = one clear moment (2-8 seconds). `character` is the main robot doing
  it (or "" for the world).
- `dialogue` beats: `character` is the speaker id, `parenthetical` how it is said, `text` the line. Each robot
  sounds like its voice and logic. Lines are short and speakable. Let silence and action carry feeling too.
- `sound` beats for important sounds only.
- `est_seconds` per beat is realistic (speech is about 2.5 words a second, plus reaction time).
- Continue naturally from the previous scene and set up the next one:
  previous: {json.dumps(scenes[i - 1], ensure_ascii=False) if i > 0 else "none (this opens the film)"}
  next: {json.dumps(scenes[i + 1], ensure_ascii=False) if i + 1 < len(scenes) else "none (this ends the film)"}
- `staging_notes`: the key camera and staging ideas for this scene in 2-4 sentences.
{("Revision notes to apply: " + notes) if notes else ""}"""
        data = ask(prompt, system=SYSTEM, schema=SCENE, effort="high", log=self.log, label=f"scene {sid}")
        data["id"] = sid
        _save(out, data)
        return data

    def scenes(self, force=False, workers=4):
        ids = [s["id"] for s in self.outline()["scenes"]]
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(lambda sid: self.scene(sid, force=force), ids))
        return [self.scene(sid) for sid in ids]

    # 4 ---------------------------------------------------------------- continuity review + rewrites
    def review(self, force=False):
        out = self.dir / "review.json"
        if out.exists() and not force:
            return _load(out)
        script = self.markdown(write=False)
        prompt = f"""<bible>
{json.dumps(self.bible(), indent=1, ensure_ascii=False)}
</bible>

<script>
{script}
</script>

You are the script editor. Read the whole script and list only the problems worth fixing before production:
continuity errors (who is where, what was known when, objects that appear or vanish), a robot acting against its
programmed logic without the story explaining it, the Tiny Robot knowingly harming anyone or any plant, setups
without payoff, scenes that drag or repeat, dialogue that is on-the-nose or out of voice, and anything outside the
production limits. For each: the scene id, the problem, and a concrete fix the scene writer can apply.
At most 12 issues; skip nitpicks. `overall` is a short honest verdict."""
        data = ask(prompt, system=SYSTEM, schema=REVIEW, effort="high", log=self.log, label="review")
        _save(out, data)
        by_scene = {}
        for it in data["issues"]:
            by_scene.setdefault(it["scene_id"], []).append(f"{it['problem']} FIX: {it['fix']}")
        known = {s["id"] for s in self.outline()["scenes"]}
        todo = [(sid, " | ".join(v)) for sid, v in by_scene.items() if sid in known]
        print(f"  review: {len(data['issues'])} issues in {len(todo)} scenes; rewriting those scenes")
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda t: self.scene(t[0], notes=t[1], force=True), todo))
        return data

    # 5 ---------------------------------------------------------------- readable script
    def markdown(self, write=True):
        bible, outline = self.bible(), self.outline()
        names = {c["id"]: c["name"] for c in bible["characters"]}
        locs = {l["id"]: l["name"] for l in bible["locations"]}
        lines = [f"# {bible['title']}", "", f"*Tag: {bible['tag']}*", "", f"> {bible['logline']}", ""]
        total = 0.0
        acts = {a["act"]: a for a in outline["acts"]}
        cur_act = None
        for s in outline["scenes"]:
            p = self.dir / "scenes" / f"{s['id']}.json"
            if not p.exists():
                continue
            sc = _load(p)
            if s["act"] != cur_act:
                cur_act = s["act"]
                lines += ["", f"## Act {cur_act}: {acts.get(cur_act, {}).get('title', '')}", ""]
            secs = sum(b["est_seconds"] for b in sc["beats"])
            total += secs
            lines += [f"### {sc['id']}. {sc['title']}",
                      f"**{locs.get(sc['location_id'], sc['location_id']).upper()}, {sc['time_of_day'].upper()}**"
                      f" · about {secs / 60:.1f} min", ""]
            for b in sc["beats"]:
                if b["type"] == "dialogue":
                    who = names.get(b["character"], b["character"]).upper()
                    par = f" *({b['parenthetical']})*" if b["parenthetical"] else ""
                    lines.append(f"**{who}**{par}: {b['text']}")
                elif b["type"] == "sound":
                    lines.append(f"*Sound: {b['text']}*")
                else:
                    lines.append(b["text"])
                lines.append("")
        lines.insert(4, f"*Running time: about {total / 60:.0f} minutes*")
        lines.insert(5, "")
        md = "\n".join(lines)
        if write:
            (self.dir / "script.md").write_text(md, encoding="utf-8")
            print(f"  script.md: {total / 60:.1f} min")
        return md


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    film = Film(args[0])
    step = args[1] if len(args) > 1 else "all"
    if step in ("bible", "all"):
        film.bible(force and step == "bible")
    if step in ("outline", "all"):
        film.outline(force and step == "outline")
    if step in ("scenes", "all"):
        film.scenes(force and step == "scenes")
    if step in ("review", "all"):
        film.review(force and step == "review")
    if step in ("md", "all", "review", "scenes"):
        film.markdown()
    if film.log.exists():
        usd = sum(json.loads(l)["usd"] for l in film.log.read_text(encoding="utf-8").splitlines())
        print(f"  Claude spend so far for this film: ${usd:.2f}")


if __name__ == "__main__":
    main()
