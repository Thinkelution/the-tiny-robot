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
- **Polish pass** (same day): turf with soil patches instead of a flat leaf texture; per-cluster colour variation;
  three tree shapes (round, column, umbrella); the sapling taller and brighter in a ring of pale stones; the crew's
  pipe from S21 on, with the bend that rises over the great root; shots keep trees away from their camera, and
  background robots are moved along Mossback's loop until a ray from the camera actually reaches them. New
  frame: S26 sunrise. Flat ground-cover slabs were dropped because from Tiny's height they read as puddles.
- **Main Square** (`blender/mainsquare.py`): slab plaza, the Big Board on two pillars above a stage of six 0.3 m
  platforms (one Tiny hop each), the Fast Lane model table, Tiny's crate lookout, the Count House with amber slit
  windows, ring roads and towers, and the Old Grove's treetops closing the view down Grove Boulevard. The Board
  shows pictures drawn by `agent/boardart.py` (the Fast Lane pitch, the Grove's red gauges, the vote).
- **Crowd** (`blender/crowd.py`): 200 boxy extras with chest lamps (off, green, red) as ONE mesh with material
  slots, so a full square costs about as much as one hero robot. A lamp cap on the shoulders lets the vote read
  from overhead. Lessons: very rounded extras looked like pillows on sausage legs (bevel cut from 30% to 8%,
  sturdier legs and feet); and the red wave in S09 has to be filmed from the stage side, because chest lamps are
  on the front.
- Look-dev frames: S03 day wide, S03 reverse down the boulevard to the Grove, S09 evening red wave, S17 overhead vote.
- New light presets: day and evening.
- **The Pipeworks** (`blender/pipeworks.py`), the first interior: a 30 x 22 x 12 m room of steel-blue and green
  square pipes, the gauge panel with its rows of round lights (the sprout and Nursery lights follow their own water
  controls), the big lever (up or down), Tiny's 0.35 m ledge, the waist-high railing with Dash's dent, the blank
  grey wall with the narrow square gap, and behind it the cramped valve room: the linkage bar, the valve that
  splits the water up to the Nursery and down toward the Grove, and the tree gauge that lights the room on its
  own. Amber warning lamps, a high window over the south doorway, Tiny's hatch, spare pipe stacks.
  Lessons: the high window was first built with opaque glass, so no sun came in; then the roof fill was about
  three times the sun on the floor, so the window patch vanished. Indoors the window is now the key light (sun
  x3, dim cool fill), and at night a hanging work lamp pools light on the lever.
- Look-dev frames: S05 afternoon, S12 wide, S12 valve room, S19 the ring of robots round the panel.
- **The Rooftop Nursery** (`blender/nursery.py`): the Seed Tower as one 20 x 20 x 24 m block on the Grove's north
  edge, and on its roof five rows of seedling trays toward the south edge, the tall tank on legs, the dry pipe
  over square brackets and down the wall, the spout and five carrying tanks by the bar-frame greenhouse, the
  ladder hatch, a low kerb, the slab ramp from the roof next door, and a work lamp for the evening scenes.
  Each tray's sprouts are one mesh with a "dry" shape key; a per-tray `health` property, driven by the water
  value delayed by the tray's distance from the tank, drives both the key and the colour (the material reads the
  object property). One keyframe makes the S06 green ripple run down the rows.
  Lessons: the roof deck sat exactly on the tower's roof face and flickered red (raised 2 cm); the building
  generator's metre-high parapet hid the Grove (`facade.tier_mesh(parapet=0)` for this tower); a haze box below
  the camera reads as a black band (it now always reaches 12 m above the camera); and from 1.5 m above the roof
  the edge hides the Grove right below, so the S06 shot is a crane over Tiny's shoulder.
- Look-dev frames: S04 reveal, S04 low among the trays, S06 sunset over the Grove, S20 night.
- **The Junk Stacks** (`blender/junk.py`): Tiny's 0.9 m crate home with a square doorway glowing warm inside and a
  plank porch facing the morning sun, the small leaning stack by the door, the slab lane east past the weed in its
  pavement crack (and Dash's skid mark, from S14 on), the scrap pile with the First Workshop's square emblem plate,
  three scrap cubes on the porch for S14, two idle gantry cranes, about 95 uneven crate towers up to 18 m kept clear
  of the clearing, the lane and the corridor toward the Grove, and the Grove's treetops far to the north-east. All
  2,000+ crates are one merged mesh with eight paint slots (`junk.boxes_mesh`). New light preset: dawn, with blue
  fog from the haze box at 20x the city density.
- Look-dev frames: S01 wide in the fog, S01 the weed at Tiny's height, S14 the porch and the scrap cubes, S30 Dash
  stopped beside the weed.
- **Fast Lane Works** (`blender/fastlane.py`, built into the Grove's city so every Grove shot sees the same road):
  dead straight along y = 0 from the west, a raised deck on piers that ramps down to a slab road one kerb above the
  street and stops 2 m short of the Grove's west gate, with rebar sticking out of the broken end, Quota's painted
  parking box, striped barriers, stacked road slabs and floodlights on square poles (lit at night). Two states:
  "straight" (S08, S21) and "curve" (S27), where the barriers are dragged into a curve that leaves the road and
  follows the ring road round the Grove's south-west corner. S21 adds the crew's pipe line through the gate.
  First idea, changed by the script: a viaduct ending in mid-air. S08 has Tiny step out of the Grove into the gap
  between Quota's lowered blade and the trees, so the road had to come down to the ground at its end.
- Look-dev frames: S08 wide down the road at the drooping Grove, S08 low with Tiny under Quota, S21 the night pipe
  race, S27 top-down on the curve.
- Continuity to settle: S21 lays the new pipe from the Fast Lane's end (west gate), while S24 has it cross the
  great tree's root on the north-east side, nearer the Pipeworks.
- **The Foundry** (`blender/foundry.py`): a 56 x 38 x 20 m hall lit orange from below by molten channels along the
  walls and a glowing pit round the Logic Press (area lights turned to face up). The Press is a cliff of slabs:
  base, anvil, four columns, crown and a raised ram on brass pistons, with a glowing plate slot (and in S28 a blank
  plate waiting in it) and a painted square floor mark. Also the rack of blank core plates, Mossback's fenced
  square pen with its worn square track and a gate that opens, floor seams, pipes along the walls, and the great
  doors in the east wall, so the S28 sunrise comes straight in as a gold bar across the floor and backlights the
  crowd in the doorway. Warden's crate with Tiny's eyes in its slot is a shared prop (`foundry.crate_with_tiny`).
  Lessons: two cameras landed inside solid geometry (a black frame both times); a quick ray test from each camera
  before rendering would catch that.
- Look-dev frames: S10 the Press and Warden from Tiny's height, S18 the orange hall and the night through the
  doors with the crate, S28 the crate under the Press, S28 the crowd in the sunrise.
- **The Count House** (`blender/counthouse.py`), the last set: a 26 x 16 x 14 m archive, the main aisle down the
  middle between 10 m shelves of data blocks (about 3,500 block fronts in one mesh: bright amber, dim amber and
  dark empty drawers, set back into the shelves), narrow side aisles, the rolling ladder on its rail, the big
  square reading screen on the west wall (bars dropping, the two footprints, the Grove's planting rows, drawn by
  `agent/boardart.py`), the low step block, the dusty emblem block, warm pendant lamps at night, and a high square
  window in the east wall so the S29 sun lies along the aisle. One green handle among the amber ones (S29).
  Lesson: glowing blocks at strength 2 turned every wall into a flat amber sheet; at 0.2-0.55 with a fifth of the
  drawers dark, the shelves read as an archive and the screen and the green handle stand out.
- Look-dev frames: S11 Tiny and Ledger at the screen, S11 the wide aisle, S29 the gold morning bar, S29 the green
  handle.

**All eight sets are now built**, each with four look-dev frames in `films/the-tiny-robot/world/lookdev/`. Next:
animation (walk cycles, the eye and antenna language, the drivers that make plants and gauges tell the story),
then shots.

## Step 9 · Animation: first test (2026-11-15)
- **`blender/anim.py`**: an `Actor` around any robot built from its spec.
  - `walk(points, start, speed)`: follows a path; the feet, the head bob, the step roll and the hand swing are
    all timed by the distance covered (a stride per 0.32 x height), so feet never skate; corners swing round eased.
  - `expr`, `blink`, `look`: the eye shape keys and the eye group sliding across the face screen.
  - `antenna`: Tiny's antenna tip keyed amber (thinking) or green (go).
  - `check`: Tiny's routine before every action: antenna amber, eyes left, eyes right, back, blink, antenna
    green, a small happy squint. About two seconds.
  - `idle`: breathing bob and blinks wherever nothing else is moving the body.
- **`blender/animshot.py`**: animated shots built on the same `setshot.stage()` as the stills (rim lights now
  ride with their robot), with `--stills` to check a few frames before rendering all of them.
- **First test, S02 beats 2-4**: Tiny trots in through the Grove's north gate, stops exactly where the pavement
  meets the grass, checks, steps onto the grass and walks round a fallen slab leaf instead of over it. 264 frames
  at 24 fps (11 s), rendered at preview size.
  Bugs: the idle pass used Tiny's last position for the frames before it first moved (it now starts from where
  the robot was placed); and facing the low morning sun from inside the south gate left everything dark and teal,
  so the entrance moved to the north gate with the sun behind the camera.
- **Owner's note on the first test: "the floor is very static... shouldn't it be wet, with give? and lighting is
  dull."** Changes:
  - dew: a thin wet clear coat over the turf (wetter in the leaf hollows, none on bare soil, less as the ground
    dries) with fine droplets that sparkle in a low sun; a light dew coat on the grass blades. The first try
    (coat 0.85, roughness 0.06) mirrored the wall like a flood; dew is a soft sheen (coat 0.32, roughness 0.3).
  - give: the grass is now built in 5 m patches, each with a "sway" shape key that leans every blade from its
    root (tips move, roots stay planted), driven by two gust waves that travel down-wind across the Grove.
  - light: the morning sun 9 -> 13 and warmer, the sky brighter, less haze.
- **Footsteps in the grass** (`plants.press_grass`, hooked in by `animshot.press`): blades within 0.85 x height of
  a walking robot's foot are pushed down, the tip most and the root not at all, and spring back when the foot
  moves on. Modifiers, so it is live every frame and adds to the wind: a "tip" vertex group, a
  VertexWeightProximity per foot, a mix, a multiply and a Displace. A dense meadow is laid along each walking
  robot's path in the shot so the feet have grass to push through.
  Bug worth remembering: VertexWeightProximity's "OBJECT" mode is the distance between the two objects' origins
  (one weight for a whole grass patch); it only seemed to work in a test whose blade sat at the world origin.
  "GEOMETRY" mode measures every vertex to the foot's mesh. With it, blades at Tiny's feet drop from 18 cm to 4 cm.

## Step 10 · The whole of S02 in one take (2026-11-15)

The full scene, B1-B17, built as one timeline in `blender/s02.py`: one Blender scene, one set, three robots,
fourteen cameras switched by timeline markers. 2,059 frames at 24 fps (about 86 s), 1280x720, 28 samples.

- **The beats**: the Grove from overhead with Mossback on its loop; Tiny at the gate, its check, the leaf;
  Mossback tips its tank to water a tree ("Good morning, little..."); Tiny waits by the sapling, Mossback comes
  round again ("...one. The sapling grew." / "I saw! It reaches my eyes now."); Primly glides in on straight lines
  and right-angle turns and sweeps the leaves and the cube seed toward the scrap chute; the seed catches on the
  chute's lip, Tiny tiptoes over, checks, hugs it, waddles back and sets it beside the sapling with a pat
  ("...mess. It is growing."); Primly's head snaps round, Tiny freezes, hands behind its back; the fanfare, and
  everyone leaves for Main Square.
- **New in the animation library** (`blender/anim.py`):
  - `place()`: put a robot somewhere new on a cut (across the Grove, further round the loop). It also trims every
    key, walk segment and busy range queued after that frame, so an earlier walk cannot drag the robot back.
    Without the trim Tiny vanished from the B3 shot: its B2 walk keys outlived the cut.
  - `rotate` (Mossback's tank tilt, Primly's head snap), `sweep` (Primly's brooms), `hands` (rest, hug, behind the
    back, up) and `carry` (a prop rides with the hands while the robot walks).
  - Blender 5 actions keep their F-curves in layers, strips and channel bags; `_fcurves()` finds them.
- **The Grove**: Mossback's loop was tightened from 44 m to 20 m across so it passes the sapling in frame; the
  look-dev frames from Step 8 have a slightly wider loop than the film now.
- **The meadow** laid along the walked paths was as tall as Tiny; it is now lawn height (blades under its eyes).
- **Encoding on the server** (`gpu-worker/worker/encode.py`): frames never come down to this PC. The worker
  pulls them from S3, draws the dialogue and sound cues as subtitles (no voices yet), encodes the MP4 with ffmpeg
  and uploads only the video.
  Lesson: the render ran on, but this PC lost its internet while it was waiting on the job, so the chained encode
  never started. Every step is a separate job, so the encode was simply run again on the frames already in S3.
- Render: about 8 s a frame on the L40S, roughly 4.5 hours for the scene.
