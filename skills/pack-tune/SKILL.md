---
name: pack-tune
description: Change recipes, add pack-only items that combine mods, and switch difficulty presets through tune.json, which packloom checks against the real item and recipe registry and compiles to KubeJS scripts. Use when a user wants a recipe cheaper or harder, a cross-mod item ("a sword made from X and Y"), an easy/normal/hard preset, or asks why a KubeJS script fails.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Write, Edit
---

# Tune recipes and difficulty

Nobody writes KubeJS by hand here. `tune.json` next to `pack.json` says what changes; `tune build` checks
every id against `registry.json` (items, item tags, recipes indexed from the pack's jars) and writes
`overrides/kubejs/startup_scripts/packloom.items.js` and `server_scripts/packloom.tune.js`.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py tune init --namespace <pack>   # adds kubejs+rhino to mods.txt, writes a tune.json skeleton
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py registry                       # index server/mods (+ vanilla and forge jars); run after every build
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py tune check                     # validate only
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py tune build [--difficulty easy|normal|hard]
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py tune verify                    # after /pack-test: did KubeJS load, any script errors
```

## tune.json

```json
{ "namespace": "techpack", "difficulty": "normal",
  "items": [{ "id": "techpack:flux_realmite_blade", "name": "Flux Realmite Blade", "type": "sword", "tier": "netherite",
              "attack_damage_bonus": 4, "rarity": "epic", "glow": true, "tooltip": ["..."], "icon": {"shape": "blade", "color": "#ff5a3c"} }],
  "recipes": [{ "id": "techpack:flux_realmite_blade", "type": "shaped", "pattern": ["F", "R", "C"],
                "key": {"F": "redstone_arsenal:flux_sword", "R": "divinerpg:realmite_sword", "C": "thermal:flux_capacitor"},
                "result": "techpack:flux_realmite_blade", "count": 1 }],
  "remove": [{"output": "ns:item"} | {"id": "ns:path"} | {"mod": "ns"}],
  "replace_inputs": [{"in": {"output": "quarryplus:quarry"}, "from": "#forge:ender_pearls", "to": "#forge:dusts/redstone"}],
  "presets": {"easy": {"recipes": [], "remove": [], "replace_inputs": []}, "hard": {...}} }
```

- `items`: `type` basic | sword | pickaxe | axe | shovel | hoe | helmet | chestplate | leggings | boots; tools and
  armor take `tier` wood..netherite. `icon` draws a 16x16 placeholder (blade, ingot, gem, orb, tool) that a
  real PNG at `overrides/kubejs/assets/<ns>/textures/item/<name>.png` replaces (never overwritten).
- `recipes`: `shaped`, `shapeless` (`inputs` list) or `custom` (`json` is a raw recipe, for machine recipes:
  `{"type": "thermal:pulverizer", ...}`). Ingredients are item ids or `#tags`.
- `remove` and `replace_inputs.in` are KubeJS filters: `id`, `mod`, `output`, `type`, `input`. `tune check`
  tells how many recipes each one touches and refuses a filter that touches none.
- `presets`: rules added on top of the base for that difficulty. Items are never per preset.

## How to work

1. Find ids in `registry.json` (`grep '"thermal:flux' registry.json`), never from memory; `tune check` prints
   "did you mean" for near misses.
2. For a difficulty preset, prefer `replace_inputs` with tags (`#forge:ingots/iron` → `#forge:ingots/gold`) over
   removing recipes: the recipe stays discoverable in JEI. Never make a chain circular (an alloy that needs the
   machine that makes the alloy); check the target's own recipe in `registry.json` first.
3. `tune build`, then `/pack-build` and `/pack-test`, then `tune verify`. A script error shows up as a
   `kubejs-script` suspect in the smoke report with the line from the log.
4. Switching difficulty on a live server: `tune build --difficulty hard`, rebuild, copy
   `kubejs/server_scripts` to the server, restart. Worlds and quest progress keep going.
