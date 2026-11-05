# Integrations: the standard for a pack with more than one line

A modpack with a tech line and an RPG line is two games in one folder until something makes them touch.
`tune.json` has a place for that: **integrations**, each one a self-contained bridge between two or more mods
with its own items, recipes and rules. packloom checks every id, generates the KubeJS, writes
`INTEGRATIONS.md` for the players and feeds the quest generator.

```json
{ "id": "divine-ores-thermal", "title": "Thermal grinds Divine ores",
  "bridges": ["thermal", "divinerpg"], "tier": "early",
  "why": "DivineRPG ores only smelt 1:1. The Pulverizer turns realmite ore into two dusts...",
  "items":   [ { "id": "techpack:realmite_dust", "name": "Realmite Dust", "icon": {"shape": "dust", "color": "#e04a3a"} } ],
  "recipes": [ { "id": "techpack:pulverize_realmite_ore", "type": "custom",
                 "json": { "type": "thermal:pulverizer", "ingredient": {"tag": "forge:ores/realmite"},
                           "result": [{"item": "techpack:realmite_dust", "chance": 2.0}] } } ],
  "remove": [], "replace_inputs": [] }
```

| Field | Meaning |
|---|---|
| `id`, `title` | unique id, the name players see in INTEGRATIONS.md and the quest book |
| `bridges` | the mod ids (namespaces) it connects; at least two; `tune check` warns if one defines no item in the registry |
| `tier` | `early`, `mid` or `late`: where in the pack it belongs |
| `why` | one or two sentences: what problem it solves for the player |
| `items`, `recipes`, `remove`, `replace_inputs` | the same shapes as at the top level of tune.json |

Integrations are merged first, then the base lists, then the difficulty preset. They are part of the base:
every difficulty has every integration; presets change their inputs.

## How many, and which kinds

A pack with lines A, B and C should have **at least two bridges per pair of lines that a player will run at
the same time**, and 16 to 24 integrations in all for a three-line pack. Fewer than that and the lines never
meet; more and the pack has a third line called "the integrations". Five kinds cover almost everything:

1. **Processing**: one mod's machine processes another mod's material. Ore doubling of the RPG mod's ores in
   the tech mod's machines is the first thing to do; it also fixes the RPG mod's grind.
2. **Material**: an alloy or plate that needs both mods' materials, made in one mod's machine. This is what
   the new tools and armor are made of.
3. **Gear**: tools, weapons, armor from the material, crafted in the vanilla shapes so JEI explains them.
4. **Automation**: one mod automates another's farm or kitchen (the Insolator grows Farmer's Delight crops).
5. **Alternative route**: a second recipe for an expensive block, paid in the other line's currency (a Quarry
   from Thermal frames instead of 32 diamonds).

Rules that keep it honest:

- Every pack-only item must be reachable from both lines: if the ingot needs a Thermal machine, its tools must
  be useful to a DivineRPG player, or nobody crosses.
- Numbers come from the mods' own recipes: look at how Thermal doubles copper (`chance: 1.25` on raw,
  `2.0` on ore) and do the same for the new metal. Do not invent a better ratio.
- No circular chains and no removals of a mod's own recipe to force a bridge; a bridge is an addition.
- Placeholder icons are fine to ship; `INTEGRATIONS.md` lists the items so an artist knows what to draw.
- Difficulty goes through `replace_inputs` on the integration's own recipes (`"in": {"id": "techpack:..."}`):
  packloom bakes those swaps into the generated recipe, so even a machine recipe KubeJS cannot edit follows the
  preset.

## Checking

```
$ packloom tune check
tune.json (difficulty normal): 12 item(s), 52 recipe(s), removes 0, replaces inputs in 0 recipe(s), 19 integration(s)
bridging ae2+mekanism, ae2+thermal, ae2+thermal_extra, bigreactors+mekanism, divinerpg+mekanism, ... : OK
```

`tune check` fails on an unknown item id or recipe type shape, an integration without `bridges`, a duplicate
id, and an integration with nothing in it. It warns when a bridge names a mod that is not in the pack, and
when a custom recipe uses a tag the registry does not know as an item tag (fluid and chemical tags are
expected there and are not errors). After the server run, `tune verify` compares the number of recipes the
server added with the number tune.json expects, so a recipe JSON that a mod rejected is caught.

## The players' side

`packloom tune doc` writes `INTEGRATIONS.md`: a table of mod pairs, then every integration by tier with its
items and recipes in one line each (`forge:ores/realmite -> techpack:realmite_dust x2 (thermal:pulverizer)`).
A quest generator can read the same `integrations` list and make one quest per bridge; TechPack's does, in a
"Bridges" chapter.

## TechPack's 19

| Pair | Integrations |
|---|---|
| thermal + divinerpg | Thermal grinds Divine ores, Bloodgem from both lines, Fluxed Realmite alloy, Fluxed Realmite tools, Flux Realmite Blade |
| mekanism + divinerpg | Mekanism enriches Divine ores, Bloodgem, Osmic Arlemite plate, Osmic Arlemite armor |
| thermal + mekanism | Mekanism processes Thermal metals (silver, nickel) |
| thermal + ae2 | Thermal grinds AE2 crystals; Crystals from the Crystallizer (Thermal Extra) |
| mekanism + ae2 | Mekanism doubles silicon |
| thermal + farmersdelight | Insolator grows Farmer's Delight |
| mekanism + farmersdelight | Mekanism in the kitchen |
| thermal + forestry, mekanism + forestry | combs through the Centrifuge and the Sawmill |
| mekanism + bigreactors | Mekanism enriches yellorite |
| mekanism + redstone_arsenal | Flux from the Metallurgic Infuser |
| quarryplus + thermal | A quarry built from Thermal parts |

12 pack-only items, 52 recipes, three difficulty presets that swap inputs inside them (easy: armor from
Arlemite ingots, copper in the alloy; hard: Enderium in the alloy, Infused Alloy in the plate, blaze rods in
the tools).
