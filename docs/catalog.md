# The catalog

`catalog/families.json` is the knowledge `design` works from: **families** of mods that do one job each,
with the tags a person's wish maps to, how grindy and how heavy they are, and the exact `mods.txt` lines per
`<minecraft>/<loader>`. 80 families, 265 mod lines for 1.20.1 Forge and Fabric, every slug verified on
Modrinth. It is still an opinion, not a database: one family per job, add-ons listed but not forced, no grind
by default. The breadth is there so that `design` knows a mod exists when someone asks for it ("something
like Immersive Engineering", "the Aether", "Macaw's furniture") and can say what it costs.

```json
{
  "id": "ae2", "title": "Applied Energistics 2",
  "tags": ["tech", "storage"],
  "group": "storage-core",          // optional: families in one group do the same job; the highest priority wins
  "priority": 9,                    // tie-breaker inside a group and the order in the proposal
  "default": false,                 // true: in every proposal (qol, perf, balance, logistics, textures)
  "pick": "core",                   // core (default): a wanted tag picks it; extra: only `--include <id>` does, design lists it as available
  "grind": "low",                   // low | medium | high; --grind low drops high unless --include'd
  "power": "mid",                   // early | mid | late | endgame | any: where its best gear or machines dominate; design's ladder and balance notes
  "weight": "medium",               // light | medium | heavy; tier low allows light, mid allows medium
  "summary": "digital storage, terminals, autocrafting",
  "when": "once chests overflow, usually chapter 3-4 of a tech pack",
  "mods":   { "1.20.1/forge": ["ae2"], "1.20.1/fabric": ["ae2"] },
  "addons": { "1.20.1/forge": [["extended-ae", "bigger pattern providers"], ["mega", "huge cells"]] },
  "pairs_with": ["thermal", "mekanism"],
  "tune_hint": "..."                // shown as a warning for grind=high families
}
```

`mods` lines use the full `mods.txt` syntax, so `ftb:`, `url:`, `manual:` and trailing comments are fine;
`manual:` is how CurseForge-only mods (Twilight Forest, Flux Networks) stay in the catalog honestly.

## Adding a family

1. Add the entry. Tags must come from the `tags` map at the top of the file (add a tag there if a new kind of
   wish appears).
2. `packloom catalog verify --family <id>` with a pack of the target game and loader: every Modrinth slug must
   resolve to a version. A slug that fails is wrong or the mod is not on Modrinth; use `manual:`.
3. `python3 -m unittest discover -s tests`: the catalog test parses every line and checks every tag.
4. If the family does the same job as an existing one, give both the same `group` and decide the priority.

## What the tags mean

`packloom catalog tags` prints them. The ones that matter for `design`: `tech`, `storage`, `magic`, `rpg`,
`adventure`, `combat`, `mobs`, `survival`, `farming`, `food`, `worldgen`, `decor`, `coop`, `quests`, `visual`.
Defaults in every proposal: `qol` (recipe viewer, inventory sorting, keybind search, backpacks...), `perf`,
`balance` (Almost Unified + Polymorph), `logistics` and `textures` (Faithful 32x, shipped enabled). `tune` is
the KubeJS layer that `tune init` adds by itself.

## Groups: the same job, one winner

| Group | Families (priority) |
|---|---|
| `tech-core` | thermal (10), create (8) |
| `storage-core` | ae2 (9), refined-storage (7) |
| `tools-forge` | tinkers (8), silent-gear (6) |
| `food-core` | food = Farmer's Delight (8), pams (4) |
| `combat-core` | combat = Better Combat (7), epic-fight (5) |
| `map-core` | map = Xaero's (8), journeymap (7) |
| `shaders-core` | shaders = Complementary (8), bsl (6), photon (4) |
| `chisel-core` | chisel = Chipped (6), rechiseled (5) |
| `survival-core` | survival (4) |
| `reactors-core` | reactors (6) |

`--include <loser>` swaps the winner. Families outside a group coexist (Occultism next to Botania is fine).

## Core and extra

A tag picks only the **core** families (30 of the 80: the one-per-job opinion, Thermal rather than Immersive
Engineering, Better Combat rather than Epic Fight, Alex's Mobs rather than Naturalist). The other 50 are
**extra**: `design` prints them under "also in the catalog for these tags" and they come in with
`--include <id>`. That is what keeps a `--want tech,rpg` proposal at 18 families instead of 40 while the
catalog still knows that Ad Astra, the Aether and Mahou Tsukai exist.

## Families by area

- **Tech**: thermal, create, mekanism, ae2, refined-storage, ie (Immersive Engineering), industrial-foregoing,
  powah, pneumaticcraft, space (Ad Astra), draconic, enderio, tinkers, silent-gear, reactors, quarry, rftools,
  logistics (+ sophisticated/functional storage, routers, XNet, iron furnaces, Tom's storage), crops (Mystical
  Agriculture, Botany Pots).
- **Magic**: botania, ars, occultism, blood-magic, irons-spells, hexerei, malum, forbidden-arcanus, mahou,
  mana-artifice, evilcraft; apotheosis and artifacts for RPG loot.
- **RPG and adventure**: divinerpg, twilight, aether, undergarden, deeper-darker, blue-skies, alexs-caves,
  bosses (Cataclysm, Mowzie's), dragons (Ice and Fire), structures (When Dungeons Arise, Towns and Towers,
  CT villages, Dungeons and Taverns + Repurposed Structures, IDAS, Dungeon Crawl), aircraft.
- **Mobs**: alexs-mobs, naturalist, villages (Guard and Easy Villagers).
- **Combat**: combat (Better Combat), epic-fight, weapons (Simply Swords).
- **Farming and food**: bees (+ Bumblezone), food (+ Farmer's Respite, Cooking for Blockheads), lets-do, pams,
  crops, fishing, seasons, survival.
- **World**: worldgen (Terralith, BOP, Tectonic, YUNG's x9, Nullscape, Incendium).
- **Decor**: supplementaries, quark, macaws (11 mods), chisel, rechiseled, furniture, framed.
- **Coop and QoL**: coop (FTB x4, voice, waystones, corpse, comforts + Ping Wheel, No Chat Reports), map,
  journeymap, qol (+ Crafting Tweaks, Better Advancements, JEP, Jade addons, Carry On), backpack, balance.
- **Performance and visuals**: perf (+ Saturn), textures, shaders, bsl, photon, animations (Fresh Animations +
  EMF + ETF), audio (Sound Physics, AmbientSounds), ambience, horizons (Distant Horizons).

Not on Modrinth, so not in the catalog as slugs: Twilight Forest and Flux Networks (`manual:` lines),
Compact Machines, Immersive Petroleum, Croptopia, Mob Grinding Utils. Add them with `manual:` when a pack
needs them.
