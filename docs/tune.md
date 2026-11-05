# tune.json: recipes, items and difficulty as data

`tune.json` lives next to `pack.json`. `packloom tune build` validates it against `registry.json` and writes
two KubeJS scripts plus placeholder textures into `overrides/kubejs/`. The scripts carry a header saying so;
edit `tune.json`, not them.

## Shape

```json
{
  "namespace": "techpack",
  "difficulty": "normal",
  "items": [
    { "id": "techpack:flux_realmite_blade", "name": "Flux Realmite Blade",
      "type": "sword", "tier": "netherite", "attack_damage_bonus": 4, "attack_speed": -2.4,
      "rarity": "epic", "glow": true, "tooltip": ["Realmite edge on a flux core"],
      "icon": { "shape": "blade", "color": "#ff5a3c" } }
  ],
  "recipes": [
    { "id": "techpack:flux_realmite_blade", "type": "shaped",
      "pattern": ["F", "R", "C"],
      "key": { "F": "redstone_arsenal:flux_sword", "R": "divinerpg:realmite_sword", "C": "thermal:flux_capacitor" },
      "result": "techpack:flux_realmite_blade", "count": 1 },
    { "type": "shapeless", "inputs": ["minecraft:stick", "#forge:ingots/iron"], "result": "minecraft:iron_sword" },
    { "type": "custom", "json": { "type": "thermal:pulverizer", "ingredient": {"item": "minecraft:cobblestone"},
                                  "result": [{"item": "minecraft:sand"}], "energy": 2000 } }
  ],
  "remove": [ { "output": "mod:item" }, { "id": "mod:path/to/recipe" }, { "mod": "mod" } ],
  "replace_inputs": [ { "in": { "output": "mekanism:metallurgic_infuser" }, "from": "#forge:ingots/osmium", "to": "#forge:ingots/iron" } ],
  "presets": {
    "easy": { "recipes": [], "remove": [], "replace_inputs": [ ... ] },
    "hard": { "recipes": [], "remove": [], "replace_inputs": [ ... ] }
  }
}
```

### items

| Field | Values | Note |
|---|---|---|
| `id` | `namespace:path` | must not exist in any mod (checked) |
| `name` | text | display name |
| `type` | `basic`, `sword`, `pickaxe`, `axe`, `shovel`, `hoe`, `helmet`, `chestplate`, `leggings`, `boots` | default `basic` |
| `tier` | `wood` … `netherite` | tools and armor |
| `attack_damage_bonus`, `attack_speed` | numbers | tools |
| `rarity` | `common`, `uncommon`, `rare`, `epic` | name color |
| `glow` | bool | enchanted shimmer |
| `max_stack` | int | basic items |
| `tooltip` | list of lines | |
| `icon` | `{ "shape": blade \| ingot \| gem \| orb \| tool, "color": "#rrggbb" }` | a 16×16 placeholder PNG, written once; drop a real PNG at `overrides/kubejs/assets/<ns>/textures/item/<path>.png` and it is kept |

Items are never per preset: a world made on `easy` must still have every item on `hard`.

### recipes

- `shaped`: `pattern` rows of single characters, `key` maps each to an item id or a `#tag`, `result`, `count`.
- `shapeless`: `inputs` list, `result`, `count`.
- `custom`: `json` is a raw recipe JSON (machine recipes of any mod); its type is passed through, every
  `item`/`tag` reference inside is checked.
- `id`: optional recipe id; give one when another rule or a quest will refer to it.

### remove and replace_inputs

Filters are KubeJS's: `{"id": …}`, `{"mod": …}`, `{"output": …}`, `{"type": …}`, `{"input": …}`; several keys
AND together. `tune check` runs the filter against the registry and prints how many recipes it hits, and fails
when it hits none, so a rule that silently does nothing cannot ship. `replace_inputs` additionally requires
that the matched recipes actually use `from`.

### presets and difficulty

`difficulty` picks which preset's rules are added on top of the base rules. `tune build --difficulty hard`
sets it and builds. There is nothing magic about the names: `normal` is "base only"; `easy` and `hard` are
whatever rules you put there. Good levers, in order of preference:

1. `replace_inputs` with tags: `#forge:ingots/iron` → `#forge:ingots/gold` keeps the recipe discoverable in JEI.
2. `recipes` that add a cheaper or alternative path.
3. `remove`, last: a removed recipe is a dead end in JEI with no explanation.

Never make a chain circular (an alloy that needs the machine that makes the alloy). Look at the target's own
recipe in `registry.json` before swapping an input.

Only vanilla recipe types (`minecraft:crafting_shaped`, `crafting_shapeless`, `smelting`, `blasting`,
`smoking`, `campfire_cooking`, `stonecutting`, `smithing_transform`) are edited reliably by `replace_inputs`
and `remove`. A mod's own type (QuarryPlus's `workbench_recipe`, Thermal machine recipes) may be matched by
the registry yet ignored by KubeJS; `tune check` warns about it and `tune verify` compares counts after the
run. For those, add a `custom` recipe of that type instead and remove the original by `id`.

## registry.json

`packloom registry` indexes `server/mods/*.jar` plus the vanilla data jar and the loader jar (so `minecraft:`
ids and `#forge:` tags are known). It holds `item`, `block`, `entity` (id → display name), `dimension`, `tag`
(item tags) and `recipe` (id → `{type, result, inputs}`). Rebuild it after every `build --server`. It is also
what a quest generator should check item ids against.

## What the server says

`packloom tune verify` reads the smoke-test log and `server/logs/kubejs/*.log`:

```
kubejs seen: True; server: added 1, removed 0, modified 2, failed 0; tune.json expects added 1, removed 0, modified 2; 0 script error(s)
```

`failed recipes` > 0, a count that differs from what tune.json expects, or a script error exits 1, and `pack-test` lists the error line as a `kubejs-script`
suspect. The client needs the same `kubejs/` folder, which the mrpack's overrides carry.
