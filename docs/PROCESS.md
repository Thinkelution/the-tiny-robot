# Production diary

How The Tiny Robot is being made, step by step, with costs and mistakes. Newest steps at the bottom.

## 2026-11-14 · The goal
The owner's brief: make an entire animated short film with Blender and Claude, without manual intervention.
Title *The Tiny Robot*, tag *Truthful*, about 30 minutes. A world of robots, each programmed with a different logic;
a tiny old robot that is only a head with two small hands and feet, whose base logic is
"Do things, but do not cause harm to anyone or hurt anyone knowingly", and which knows trees and plants are alive.

Ground rules the owner set:
- Script first, then the robot characters (spec + logic), then the world.
- Models and world simple and boxy; the output and texture mapping studio quality.
- World detail from generated images plus shaders.

## Step 1 · Script (Claude via the API)
`agent/story.py`, model Claude Opus 5.5, structured JSON outputs, adaptive thinking.

1. **Bible** (world, how logics work, 8 robots, 8 locations, motifs, ending): 1 call, $0.41, 4 min.
2. **Outline**: 31 scenes in 3 acts, about 30 minutes.
3. **Scenes**: every scene as timed beats (action / dialogue / sound), written 4 at a time.
4. **Script editor review** of the whole script: 12 issues in 10 scenes (continuity, motivations, a long ending).
   Flagged scenes are rewritten automatically.

Every prompt carries the production limits (boxy robots, animatable actions only, no crowds of hundreds, no
readable text needed), so the story stays buildable.

**Hiccup:** the API key hit its monthly spending limit after $9.81 (script plus robot specs). The last two scene
rewrites and the automatic robot reviews did not run. We switched to doing those Claude steps inside the Claude
Code session instead of through the API (see Step 3).

## Step 2 · Robot characters
`agent/cast.py` asks Claude to design each robot as a parts list: boxes and cylinders with joints and roles,
2-5 materials, a face screen with animated eyes, and surface details. `blender/robot.py` builds it;
`blender/turnaround.py` renders a Cycles studio turnaround and an expression sheet.

Bugs found by looking at renders:
- The studio was overexposed, so cream read as white and cyan eyes blew out.
- Corner bolts floated outside rounded heads.
- Eye expression shape keys were blended by default (fixed by zeroing every key).
- Single visor eyes were stretched 1.6x past the screen (now clamped to fit).
- Blender saved renders to `C:\films` when given a relative path (now absolute).

## Step 3 · Review by Claude in session
With the API blocked, Claude (in Claude Code) reviewed every turnaround against the bible:
- Tiny's hands looked like cups with lids: now mitten hands with a front thumb.
- Dash read as a toy jeep: now a stepped wedge with big rear wheels and a resting squint.
- Primly's brooms floated at the waist: its arms now angle forward to push floor brooms.
- Shine got huge eyes ("huge simple expressions").
- Two scene fixes from the editor's notes (S13 motivations; S30 cut to a short bridge; S09 and S20 adjusted so the
  finale's payoffs land).

## Step 4 · Studio texture library
- **Generation:** FLUX.2 [klein] 4B (Apache-2.0) on a stop-when-idle cloud GPU (L40S), about 1.5 s per
  1024 px image. 32 images: worn and clean paint, brushed steel, old brass, rubber, grime and rust streaks,
  scratches, glass fingerprints, paint chips. Prompts: [textures/library.json](../textures/library.json).
- **Maps:** `textures/build.py` crops plate borders, flattens photo lighting, makes each image seamless, and derives
  height and normal maps.
- **Materials:** `blender/texmat.py` layers them through each part's UVs:
  - paint colour modulated by the paint photo;
  - chip patches and edge wear revealing brushed steel;
  - scratches through the paint;
  - grime streaks and crevice dirt;
  - normal-mapped relief.
  - Every part gets a random texture offset, and texture scale follows the robot's size.

Bugs on the way:
- First normal maps were nearly flat-sideways, which rendered everything black.
- Colour textures read as linear light gave a negative detail multiplier, also black.
- Chips first looked like terrazzo stone; they are now clustered in patches.
- AgX "Medium High Contrast" turned yellow to peach and red to salmon. The film now uses "AgX - Punchy".

## Costs so far
| Item | Cost |
|---|---|
| Claude API (bible, outline, 31 scenes, review, rewrites, 8 robot specs) | $9.81 |
| Cloud GPU for textures (about 15 minutes of an L40S) | about $0.60 |
| Blender, rendering on a local AMD RX 7600 | $0 |
| Claude Code session time (reviews, fixes, pipeline code) | part of the Claude plan |

## Step 5 · Repo, website, teaser (2026-11-14)
- **Repo:** this repository went public as `Thinkelution/the-tiny-robot`. Code is MIT, film content is CC BY 4.0.
  Rendered frame sequences and the music file stay out of git.
- **Website:** `site/` deploys to [thetinyrobot.online](https://thetinyrobot.online) from a Cloudflare R2 bucket
  (`site/deploy.py` creates the bucket, the custom domain, a www-to-apex redirect and the folder rule). Images on
  the page are made from the latest renders.
- **Teaser** (`films/the-tiny-robot/teaser/teaser.json`, `agent/teaser.py`, `blender/teaser.py`): 9:16, 39.5 s.
  1. A hook that asks the $100-plan question.
  2. Each robot enters a pool of light on a dark stage with its name and logic.
  3. A group shot, then "Worth a shot!".
  4. An end card pointing to thetinyrobot.online and thinkelution.com.

  It renders in Cycles at 40 samples, about 12 s per 1080x1920 frame on the RX 7600, so 3.5 hours for the reel.
  Captions are added in post (Pillow), and the music bed comes from Eleven Music.
  - Framing bugs fixed on the way: a 9:16 frame is narrow, so fit by the horizontal field of view; Blender's
    vertical sensor fit uses the sensor height (24 mm by default), not 36 mm. A side-by-side lineup can't work in
    portrait, so the closing shot is a group shot.

## Step 6 · Look development: toward feature-film quality (2026-11-14)
The first teaser renders were clean but looked like a game, not a film. The owner said so, and asked for Pixar /
DreamWorks level. The honest gap list we worked from:
- animation acting (still the biggest gap);
- hand-crafted lighting and atmosphere;
- shape appeal;
- surface detail;
- set dressing;
- grading.

We judged every change on three hero frames: a Tiny close-up, Quota, and the full lineup (`films/the-tiny-robot/lookdev/`).

What changed, in order:
1. **Atmosphere and grade** (`blender/look.py`):
   - volumetric haze;
   - rim lights light-linked to each robot;
   - a compositor grade (bloom, slight lens distortion, warm highlights / cool shadows, vignette);
   - clear-coat on painted surfaces.
2. **Time of day presets** (`world.TOD`): dusk, night, morning (and a rainy night that was dropped: the owner
   preferred dry). **Night was chosen** for the teaser.
3. **A planned city** instead of scattered boxes:
   - the square, ring roads with lane markings and kerbs, sidewalks;
   - a street running to the horizon for depth;
   - buildings set back with alleys between them;
   - lamps on sidewalks, trees clear of walls, crates that rest on each other;
   - a `Plan` that refuses to place any prop inside a building or another prop.
4. **Real facades** (`blender/facade.py`):
   - recessed windows with reveals and sills, storey bands, shopfronts with awnings, AC units, balconies, parapets;
   - fewer, larger windows and several building types;
   - each window has its own random value, so night rooms vary (warm/cool, blinds, brightness) and day windows show
     curtains, sky reflections or dark rooms.
5. **Sky**: a gradient with clouds by day and stars by night.
6. **The studio ident** (`blender/intro.py`), starring the Tiny Robot:
   - eyes blink on, it checks left and right, hops to a button and presses it;
   - giant THINKELUTION letters light one by one (one flickers);
   - the camera racks focus and cranes back to the title on a plinth: "STUDIO", "presents". Poppins (SIL OFL), no logo.

Bugs worth remembering:
- A **world volume** stretches to infinity, so it absorbed all sunlight: the sun stopped working. Haze now lives in
  a finite box near the ground.
- The world shader's **Generated** coordinate is a direction from -1 to 1, not 0 to 1: the sky gradient sat 30-40
  degrees too high and the visible sky came out pale grey.
- Fill and rim lights scattered in the haze and turned the lineup milky; only motivated lights (lamps, key spots)
  scatter now.
- Blender's vertical sensor fit uses the 24 mm sensor height unless set; framing maths assumed 36 mm.
- A 9:16 frame can't hold a side-by-side lineup: portrait uses a group shot, 16:9 the row.
- download.blender.org refuses AWS addresses; Blender reaches the cloud GPU through our S3 bucket. Blender also
  crashes at start-up without `HOME` set (SSM runs jobs without it).

Honest status: close-ups and the ident are the closest to feature quality. Wide shots read as a believable stylised
city. Character animation is still simple; acting is the next big piece of work.

| Cost item | Amount |
|---|---|
| Cloud GPU (textures, world textures, teaser renders) | about $10 so far |
| Eleven Music (two teaser beds) | from the existing subscription |

## Step 7 · Teaser release (2026-11-15)
- **Order:** the question comes first ("Can a studio-quality animated film be made with a $100 Claude plan? Blender +
  Claude?"), then the studio ident, the eight robot intros, the lineup with "The Tiny Robot · One logic to rule
  them each." and "Worth a shot!", and an end card. 1227 frames, 40.9 s at 30 fps. The music was regenerated to fit
  this order.
- **Two variants:** 9:16 for reels (a group shot to close) and 16:9 for the websites (a staggered row).
- **Where it rendered:**
  - 9:16 on the local RX 7600, about 23 s per frame after speed settings (persistent data, fewer bounces, adaptive
    sampling). Renders resume from the last finished frame.
  - 16:9 on the cloud L40S at 12-14 s per frame. The finished video was built on the server too
    (`gpu-worker/worker/preview.py ... final` runs `Teaser.post()` with a bundled ffmpeg), so no frames were
    downloaded.
- **Fix found in review:** the Tiny Robot reached across its body to press the ident button. The button now sits on
  its camera side and it presses with the near hand.
- **Captions are post-only:** changing the question from "$20" to "$100" only needed a new post step, not a
  re-render.
- **Released** on [thetinyrobot.online](https://thetinyrobot.online/#teaser) and in a new "Open movie" section on
  [thinkelution.com](https://thinkelution.com/#movie). Videos are hosted on the site, not in git.

## Step 8 · The world: Gridhaven and the Old Grove (2026-11-15)
- **City plan first.** The script's eight locations went onto one map before anything was built
  (`films/the-tiny-robot/world/city.json`, drawn by `agent/citymap.py` as `world/map.png`). The Old Grove sits in the
  middle, as the bible says. The Rooftop Nursery is on a tower right on its north edge and the Pipeworks between
  them, so the split water valve makes physical sense. Main Square is at the end of Grove Boulevard, Quota's Fast
  Lane stops just short of the Grove wall, the Junk Stacks are on the south-west edge and the Foundry faces east
  for the S28 sunrise. Five outdoor sets share one city; three interiors are built on their own.
- **Living plants** (`blender/plants.py`): every tree, sapling, bush and grass tuft follows one control value,
  `water` from 0 to 1, through drivers. Leaves go from green through olive to brown, clusters sink, tilt out and
  shrink, blossoms open above 0.85, and every cluster sways on its own phase. The gauge lights on the water-line
  grates read the same value (green, amber, red). One keyframed number tells the whole drought and revival story.
- **The Old Grove** (`blender/grove.py`): a 64 m walled clearing, about 70 box-trunk trees, the great old tree with
  its root arching over the water line, the sapling at the centre, Mossback's worn loop, grates, bushes and
  26,000 grass blades, with the city around it.
- **Look-dev stills** (`blender/setshot.py`): S02 morning, S07 drought and S31 golden morning, at Tiny's eye height.

Bugs worth remembering:
- **Grass took 302 of 313 seconds to build.** Adding blades one by one with `bmesh.ops.create_cube` to a growing
  mesh gets slower with every blade. Building plain vertex lists and calling `from_pydata` once: 11 s for the whole
  set.
- 8,000 separate leaf cubes were merged into one object per cluster (3,600 objects), which the droop and sway
  drivers move as a unit.
- A low sun behind 30 m towers leaves the whole Grove in shadow. Golden morning now comes in higher from the east,
  and the sunrise runs straight down Grove Boulevard, the one long gap in the skyline.
