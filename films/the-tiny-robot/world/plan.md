# Gridhaven: world build plan

The city layout is in [city.json](city.json), drawn as [map.png](map.png) by `agent/citymap.py`.

## One city, three interiors
- **Outdoor sets** are districts of one shared Gridhaven: Old Grove, Rooftop Nursery, Main Square, Fast Lane Works,
  Junk Stacks. Every wide shot sees the same skyline, and the Grove's treetops are visible from everywhere.
- **Interior sets**: Pipeworks, Count House, Foundry. Each one is built on its own; its outside sits in the city so
  doors and windows match.
- Far districts load as simple blocks; only the set in use gets full detail.

## Systems the sets share
1. **Time of day**: one sky and sun model driven by sun height and direction, with named presets for every time the
   script uses: pre-dawn, dawn, sunrise, morning, golden morning, day, afternoon, sunset, evening, dusk, night and
   late night. This replaces the four teaser presets.
2. **Living plants**: box-trunk trees, the sapling, the weed and the seedling trays share one rig with a
   `water` value from 0 to 1. Leaves droop, lose colour and drop when dry, lift when watered, and blossom at full
   health. Every plant sways in the wind. The Grove's gauge grates follow the same value (green, amber, red).
3. **Background robots**: boxy extras with chest lamps that can light green or red, enough for about 200 in Main
   Square (S09, S16, S17).
4. **Set check**: the existing `Plan` overlap check runs on every set, so nothing floats or sits inside anything else.

## Build order (most screen time first)
| # | Set | Scenes | Times of day |
|---|---|---|---|
| 1 | Old Grove (built) | S02 S07 S22 S23 S24 S26 S31 | morning, night, pre-dawn, sunrise, golden morning |
| 2 | Main Square (built) | S03 S09 S15 S16 S17 | day, evening, dusk |
| 3 | Pipeworks (interior, built) | S05 S12 S13 S19 S25 | afternoon, late night, night, pre-dawn |
| 4 | Rooftop Nursery (built) | S04 S06 S20 | afternoon, sunset, night |
| 5 | Junk Stacks (built) | S01 S14 S30 | dawn, morning |
| 6 | Fast Lane Works | S08 S21 S27 | day, night, morning |
| 7 | Foundry (interior) | S10 S18 S28 | night, morning |
| 8 | Count House (interior) | S11 S29 | night, morning |

Each set is reviewed the same way as the teaser: three hero frames from the staging notes, at Tiny's eye height,
in the scene's time of day, before it is called done.

## Open question
The script has rain in S18, S21 and S22. The teaser dropped rain. Keep the film dry, or bring rain back for those
three scenes?
