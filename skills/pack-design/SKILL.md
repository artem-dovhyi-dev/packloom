---
name: pack-design
description: Turn a description of the modpack someone wants ("RPG plus industry, some farming, a pretty world, not much grind, runs on my laptop") into a mods.txt proposal from the packloom catalog of mod families, verified against Modrinth. Use when a user describes a pack in words, asks what mods to put together, or wants a pack that fits their machine.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Write, Artifact, ArtifactData
---

# Design a pack from words

## The standard flow: the catalog page, a pick, a build

This is how a pack is designed with packloom when the Artifact tool is available. Do not interview the
person about mods in chat and do not type `design` flags from their words while the page is possible;
the page is the interface, the chat is for what the page cannot say.

1. **Render and publish the page.** One command, one publish:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/run.py catalog page --out catalog.html     # the families for the pack's game and loader
   ```

   Publish `catalog.html` with the Artifact tool, `icon` "catalog", `description` "Pick the families of
   your modpack", and `capabilities: {"db": {"rules": [{"path": "", "read": "view", "write": "admin"}]}}`
   (the owner and editors write the pick, everyone the page is shared with reads it). When a page for this
   pack was published before (the person gives its link, or `picks.json` in the pack has `artifact`), pass
   that `url` so the link stays the same. Tell the person in one line what to do on it: mark tags, choose a
   grind level, correct the cards, press **Hand to Claude**. Then stop and wait; the pick is theirs.

2. **Read the pick back.** When they say they have picked (or ask to build from the page), read the
   document with ArtifactData: `get`, the artifact's `url`, collection `picks`, doc_id `current`. Save it
   verbatim as `picks.json` in the pack folder (or the folder the pack will be created in) and add the
   artifact's `url` under the key `artifact`. The page writes:

   ```json
   { "game": "1.20.1/forge", "want": ["tech", "rpg"], "avoid": [], "include": ["create"], "exclude": [],
     "grind": "low", "difficulty": "easy", "families": ["create", "mekanism", "..."],
     "ladder": {"early": [], "mid": [], "late": [], "endgame": []}, "balance": ["2 families peak at endgame: ..."],
     "command": "design --want tech,rpg --include create --grind low --verify --write", "saved_at": "..." }
   ```

   If `get` finds no document, the page could not save in that viewer: ask them to press **Copy** on the
   page and paste the command, then write the same fields into `picks.json` by hand from that command. Never
   rebuild the pick from memory of the page; the document is the record.

3. **Run it from the file, not from retyped flags.** `init` the pack if there is none (the game and loader
   are in the document's `game`), then:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/run.py design --picks picks.json
   python3 ${CLAUDE_SKILL_DIR}/scripts/run.py design --picks picks.json --verify --write    # --force to replace mods.txt
   ```

   `--picks` fills want / avoid / include / exclude / grind and the game from the document; flags given on
   the command line win over it (`--ram 16 --gpu apple` or `--detect` for the machine). The first run shows
   the proposal, the ladder and the balance notes; read step 4 of the next section for what to say about
   them. `--write` also copies the document to `<pack>/picks.json`, so the pack remembers what was chosen on
   the page. A line starting with `! the page showed a different set` means the page's JavaScript and the
   catalog disagree: trust `design`, build, and report the difference as a bug in `catalog_page.html`.

4. **Finish the chain.** `tune build --difficulty <difficulty from the document>` when the pack has a
   tune.json; the balance notes go to `/pack-tune` as integration work; then `/pack-build` and `/pack-test`.

Changing the pick later is the same loop: the person reopens the page (same link), presses **Hand to Claude**
again, and you read `picks/current` again; `design --picks picks.json --write --force` replaces mods.txt.

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
