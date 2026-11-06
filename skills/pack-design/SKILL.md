---
name: pack-design
description: Turn a description of the modpack someone wants ("RPG plus industry, some farming, a pretty world, not much grind, runs on my laptop") into a mods.txt proposal from the packloom catalog of mod families, verified against Modrinth. Use when a user describes a pack in words, asks what mods to put together, or wants a pack that fits their machine.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Write, Artifact, ArtifactData
---

# Design a pack from words

## The catalog page: let the person pick on a board, not in a chat

When the Artifact tool is available, start here instead of asking questions: render the catalog as an
interactive page and publish it, then read the pick back.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py catalog page --out catalog.html     # 80 families for the pack's game and loader
```

Publish `catalog.html` with the Artifact tool, `icon` "catalog", and
`capabilities: {"db": {"rules": [{"path": "", "read": "view", "write": "admin"}]}}` (only the owner and
editors can write a pick; everyone the page is shared with can read it). Republish the same file to keep the
URL when the catalog changes. On the page the person marks tags (want / avoid), ticks or crosses families,
switches a group (Thermal ↔ Create), toggles no-grind, and presses **Передати Клоду**; that writes
`picks/current` into the artifact's db:

```json
{ "game": "1.20.1/forge", "want": ["tech", "rpg"], "avoid": [], "include": ["create"], "exclude": [],
  "grind": "low", "difficulty": "easy", "families": ["create", "mekanism", "..."], "ladder": {"early": [], "mid": [], "late": [], "endgame": []},
  "balance": ["2 families peak at endgame: ..."], "command": "design --want tech,rpg --include create --grind low --verify --write", "saved_at": "..." }
```

When they say they have picked (or ask to build from the page), read it: ArtifactData `get`, collection
`picks`, doc_id `current`, the artifact's url. Run the `command` field through run.py (prefix `design`
flags with the pack's `--minecraft`/`--loader` if there is no pack yet) and continue at step 4 below with the
result. If the db has no document, the page could not save (no db in that viewer): ask them to press
**Скопіювати** and paste the command. Never rebuild the pick from memory of the page; the document is the
record.

## From words, without the page

The catalog (`catalog/families.json` in the plugin) holds **families**: one entry per job (Thermal, Mekanism,
AE2, DivineRPG, Farmer's Delight, world generation, coop, quality of life, performance...). Each family has
tags, a grind level, a client weight, its mods.txt lines per `<minecraft>/<loader>` and its add-ons. The
command picks families from tags; you turn the person's words into tags.

1. Read the request and map it to tags. `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py catalog tags` lists them.
   Typical mapping: "industry, machines, automation" → `tech`; "dimensions, bosses, RPG" → `rpg`;
   "dungeons, exploring, structures" → `adventure`; "fighting should feel good" → `combat`; "animals,
   dragons" → `mobs`; "farming, bees" → `farming`; "food" → `food`; "pretty world, biomes" → `worldgen`;
   "building, furniture" → `decor`; "seasons, thirst" → `survival`; "with friends" → `coop`; "magic" →
   `magic`. Shaders, animations and sound are `visual`. `qol`, `perf`, `balance` (Almost Unified +
   Polymorph), `logistics` and `textures` (Faithful 32x) come by default.
   When the person names a mod ("like Immersive Engineering", "the Aether", "Macaw's"), find its family with
   `catalog show --family <part of the name>` and pass `--include <id>`; 80 families cover the popular mods of
   1.20.1, and a family in the same `group` as the default is swapped by `--include`.
2. Hardware: if they mention their machine, pass `--ram <GB> --gpu apple|nvidia|amd|intel`; if it is this
   machine, `--detect`. A low tier drops heavy families (Create, shaders); say so.
3. Grind: three levels, `--grind low|medium|high` (`--no-grind` = low). Low drops grind=high families
   (DivineRPG, Draconic, PneumaticCraft) unless `--include`d, and maps to the `easy` tune preset; medium is
   the authors' balance and `normal`; high keeps everything and maps to `hard`. "Busy person" → low; "long
   server, we like a wall" → high. After `design --write`, if the pack has a tune.json, run
   `tune build --difficulty <preset>` so recipes follow the chosen grind.
   The proposal ends with a **progression ladder** (early / mid / late / endgame, from each family's `power`)
   and **balance** notes: two families peaking at the same late stage (Mekanism and Draconic, DivineRPG and
   Apotheosis) means the strongest gear makes the rest decoration. Carry those notes into `/pack-tune`: give
   each a job the others need, by the standard in `docs/integrations.md` (processing, material, gear, gate).
4. Run the proposal without writing first and show it:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py design --minecraft 1.20.1 --loader forge --want tech,rpg,farming,worldgen,coop --no-grind --include divinerpg --ram 16 --gpu apple
```

   The output lists every family with the reason it is in, warnings (grindy, heavy), the skipped ones with
   why (`create: same job as thermal; pass --include create to swap`), and "also in the catalog for these
   tags": the extra families a tag does not pick (Immersive Engineering, the Aether, Occultism...). Read that
   list against what the person said; when they named one of those or something like it, add `--include`.
   Discuss swaps with the person; the choice between two families that do the same job is theirs.
5. Write it: `init` the pack if there is none, then `design ... --verify --write` (`--force` to replace an
   existing mods.txt). `--verify` asks Modrinth for a version of every slug for this game and loader and
   refuses to write while one is missing. Then `/pack-build` and `/pack-test`.

If the game or loader is not in the catalog (`catalog list` shows which `<mc>/<loader>` each family has),
say so and fall back to `/pack-add` searches; do not invent slugs. New families go into `catalog/families.json`
(see `docs/catalog.md` in the plugin) and get `catalog verify` run on them.
