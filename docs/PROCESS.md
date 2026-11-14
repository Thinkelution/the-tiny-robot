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
  1. A hook that asks the $20-plan question.
  2. Each robot enters a pool of light on a dark stage with its name and logic.
  3. A group shot, then "Worth a shot!".
  4. An end card pointing to thetinyrobot.online and thinkelution.com.

  It renders in Cycles at 40 samples, about 12 s per 1080x1920 frame on the RX 7600, so 3.5 hours for the reel.
  Captions are added in post (Pillow), and the music bed comes from Eleven Music.
  - Framing bugs fixed on the way: a 9:16 frame is narrow, so fit by the horizontal field of view; Blender's
    vertical sensor fit uses the sensor height (24 mm by default), not 36 mm. A side-by-side lineup can't work in
    portrait, so the closing shot is a group shot.
