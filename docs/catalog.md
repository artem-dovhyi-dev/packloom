# The catalog

`catalog/families.json` is the knowledge `design` works from: **families** of mods that do one job each,
with the tags a person's wish maps to, how grindy and how heavy they are, and the exact `mods.txt` lines per
`<minecraft>/<loader>`. It is an opinion, not a database: one mod per job, few add-ons, no grind by default.

```json
{
  "id": "ae2", "title": "Applied Energistics 2",
  "tags": ["tech", "storage"],
  "group": "storage-core",          // optional: families in one group do the same job; the highest priority wins
  "priority": 9,                    // tie-breaker inside a group and the order in the proposal
  "default": false,                 // true: in every proposal (qol, perf, logistics)
  "grind": "low",                   // low | medium | high; --no-grind drops high unless --include'd
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

`packloom catalog tags` prints them. The ones that matter for `design`: `tech`, `magic`, `rpg`, `farming`,
`food`, `worldgen`, `coop`, `visual`; `qol` and `perf` are defaults; `tune` is the KubeJS layer that
`tune init` adds by itself.
