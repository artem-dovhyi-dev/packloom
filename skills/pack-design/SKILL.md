---
name: pack-design
description: Turn a description of the modpack someone wants ("RPG plus industry, some farming, a pretty world, not much grind, runs on my laptop") into a mods.txt proposal from the packloom catalog of mod families, verified against Modrinth. Use when a user describes a pack in words, asks what mods to put together, or wants a pack that fits their machine.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Write
---

# Design a pack from words

The catalog (`catalog/families.json` in the plugin) holds **families**: one entry per job (Thermal, Mekanism,
AE2, DivineRPG, Farmer's Delight, world generation, coop, quality of life, performance...). Each family has
tags, a grind level, a client weight, its mods.txt lines per `<minecraft>/<loader>` and its add-ons. The
command picks families from tags; you turn the person's words into tags.

1. Read the request and map it to tags. `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py catalog tags` lists them.
   Typical mapping: "industry, machines, automation" → `tech`; "dimensions, bosses, RPG" → `rpg`;
   "farming, bees" → `farming`; "food" → `food`; "pretty world, biomes" → `worldgen`; "with friends" → `coop`;
   "magic" → `magic`. Shaders and textures are `visual`. `qol` and `perf` come by default.
2. Hardware: if they mention their machine, pass `--ram <GB> --gpu apple|nvidia|amd|intel`; if it is this
   machine, `--detect`. A low tier drops heavy families (Create, shaders); say so.
3. Grind: "not much grind", "busy person" → `--no-grind`. That drops grind=high families (DivineRPG);
   if they asked for one by name, keep it with `--include divinerpg` and point at its tune hint.
4. Run the proposal without writing first and show it:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py design --minecraft 1.20.1 --loader forge --want tech,rpg,farming,worldgen,coop --no-grind --include divinerpg --ram 16 --gpu apple
```

   The output lists every family with the reason it is in, warnings (grindy, heavy) and the skipped ones with
   why (`create: same job as thermal; pass --include create to swap`). Discuss swaps with the person; the
   choice between two families that do the same job is theirs.
5. Write it: `init` the pack if there is none, then `design ... --verify --write` (`--force` to replace an
   existing mods.txt). `--verify` asks Modrinth for a version of every slug for this game and loader and
   refuses to write while one is missing. Then `/pack-build` and `/pack-test`.

If the game or loader is not in the catalog (`catalog list` shows which `<mc>/<loader>` each family has),
say so and fall back to `/pack-add` searches; do not invent slugs. New families go into `catalog/families.json`
(see `docs/catalog.md` in the plugin) and get `catalog verify` run on them.
