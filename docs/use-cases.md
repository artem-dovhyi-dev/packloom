# Use cases

Five things people ask for, and what packloom does for each. Commands are shown as the CLI
(`alias packloom='PYTHONPATH=/path/to/packloom/lib python3 -m packloom'`); in Claude Code the matching
skill runs the same command and talks you through the choices. Output below is real, from TechPack 1.2.0.

## 1. "I want a pack like this" → a mod list

> RPG and industry in parallel, some farming, a pretty world, not much grind, for four friends, on my M1.

Words become tags, tags pick **families** from the catalog (one family per job: Thermal, Mekanism, AE2,
DivineRPG, bees, Farmer's Delight, world generation, coop, quality of life, performance...). Hardware drops
heavy families, `--no-grind` drops grindy ones unless you name them.

```
$ packloom design --want tech,rpg,farming,food,worldgen,coop --no-grind --include divinerpg --detect
Proposal for Minecraft 1.20.1 forge (tier mid): 15 families, 73 mods.txt lines

+ Thermal Series [thermal]: wants tech
    ores and alloys, machines and dynamos, ducts, farming machines, Fluxbore and jetpack
+ Quality of life [qol]: default for every pack
+ Performance [perf]: default for every pack
+ Mekanism [mekanism]: wants tech
+ Applied Energistics 2 [ae2]: wants tech
+ DivineRPG [divinerpg]: asked for by id; wants rpg
    ! grindy by default: 4 boss fragments = 1 soul instead of 8 (pack config)
+ FTB coop and quests [coop]: wants coop
…
skipped:
  - create: heavy for a mid-tier machine
```

Every family comes with its add-ons and a one-line reason, so the person sees *why* 73 lines, not just 73
lines. `--verify` asks Modrinth for a version of every slug for this game and loader; `--write` writes
`mods.txt` grouped by family with comments. Swapping Thermal for Create is `--include create`.

What is not automatic: taste. The catalog is one opinion (one mod per job, few add-ons); the conversation is
where "I'd rather have Create" happens.

## 2. "Make it easier / harder" and "a sword that combines two mods" → tune.json

Recipes are data in `tune.json`; packloom checks every id against `registry.json` (16 082 recipes, 8 822
items, 1 477 item tags indexed from TechPack's jars) and writes the KubeJS scripts.

```
$ packloom tune check --difficulty hard
tune.json (difficulty hard): 1 item(s), 1 recipe(s), removes 0, replaces inputs in 2 recipe(s): OK
  replace_inputs #1: #forge:ingots/iron -> #forge:ingots/gold in 1 recipe(s): thermal:machine_frame
  replace_inputs #2: #forge:ingots/iron -> #forge:ingots/gold in 1 recipe(s): mekanism:metallurgic_infuser
```

A typo is caught before any server starts:

```
  ERROR recipe #1 (techpack:flux_realmite_blade) key C: unknown item thermal:flux_capacitorr
        (did you mean thermal:flux_capacitor, thermal:flux_capacitor_2, thermal:flux_capacitor_1?)
```

The cross-mod item in TechPack: a Flux Sword (Redstone Arsenal) over a Realmite Sword (DivineRPG) over a Flux
Capacitor (Thermal) make the **Flux Realmite Blade**, netherite tier, +4 damage, with a generated placeholder
icon until someone draws a real one. On the server:

```
[KubeJS Startup/]: Loaded 1/1 KubeJS startup scripts in 0.233 s with 0 errors and 0 warnings
[KubeJS Server/]: Added 1 recipes, removed 0 recipes, modified 0 recipes, with 0 failed recipes in 386.0 ms
```

Difficulty is a preset: `easy` and `hard` add rules on top of the base. Switching is
`tune build --difficulty hard`, rebuild, restart; worlds keep going because items never change per preset.
After the run, `tune verify` compares what tune.json expects with what the server reports:

```
$ packloom tune verify
kubejs seen: True; server: added 1, removed 0, modified 2, failed 0; tune.json expects added 1, removed 0, modified 2; 0 script error(s)
```

That comparison exists because of a real miss: a first draft swapped an input of the QuarryPlus quarry, whose
recipe has the mod's own type (`quarryplus:workbench_recipe`); the registry matched it, KubeJS could not edit
it, and the server said `modified 1`. Now `tune check` warns on such types and `verify` reports the mismatch.
Reference: [tune.md](tune.md).

## 3. "It has to run on my laptop" → hardware profile

```
$ packloom hardware
16 GB RAM, gpu=apple, cpu=Apple M1 Pro (darwin) -> tier mid
  client heap: 6144 MB   shaders: low or medium preset   mod ceiling: ~130
  note: Apple Silicon: no OptiFine (not on Modrinth, breaks Forge mods); Embeddium + Oculus run shaders fine
  note: keep the system input source on English when launching, macOS names keys after it
```

`--apply` writes `memory_mb` and `hardware` into `pack.json` and adds the performance family to `mods.txt`.
`design --detect` or `--ram 8 --gpu intel` uses the tier to drop heavy families for someone else's machine.

## 4. "Which key does what?" → keybinds as data

`packloom keys` reads the instance's `options.txt` and renders `keybinds.html`: a Mac keyboard where hovering
a key shows the actions and mods on it, clicking a mod lights its keys, and chips filter by game stage so
MekaSuit keys stay hidden until you own one. `keybinds.json` holds the layout and notes; `keys --apply` writes
the layout back into the instance with the game closed. TechPack: 104 bound, 3 conflicts, all inside JEI menus.

## 5. "Does it start?" → build, test, triage

```
$ packloom build --server
TechPack-1.2.0.mrpack: 85 files, forge 47.4.28
  MANUAL  flux-networks: CurseForge only
server mods: server/mods (80 jars); server overrides: 11 entries synced

$ packloom test --skip-build
OK: server came up in 30s; errors 4, warnings 29
```

`test` installs the loader server, finds or downloads the right Java, starts headless, waits for `Done`, stops,
and writes `smoke-report.json` with every error line and **suspects**: mixin failures, missing dependencies,
duplicate mods, stack traces mapped to mod ids, KubeJS script errors. `triage --client` does the same on
Prism's `latest.log` and crash report after a client crash. The four errors above are known benign ones (a
client-only mixin on the server, a DivineRPG tag, two loot tables); the report lists them so you can say so.

## What stays manual

CurseForge-only mods (`manual:` lines show up in the build report), accepting the Minecraft EULA
(`test --accept-eula`), drawing real item textures, and the game itself: packloom never launches the client.
