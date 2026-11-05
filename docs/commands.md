# Commands

`PYTHONPATH=lib python3 -m packloom [--pack <dir>] <command>`. Without `--pack`, the pack is the folder
holding `pack.json` nearest to the current directory (itself, a direct child, or a parent).
Every command has `--help`.

| Command | Does | Writes |
|---|---|---|
| `init --name N --minecraft 1.20.1 --loader forge [--memory 6144]` | new pack | `pack.json`, empty `mods.txt`, `overrides/` |
| `catalog [list\|show\|tags\|verify] [--family id]` | families of mods; `verify` checks every slug on Modrinth for the pack's game and loader | |
| `design --want tags [--avoid tags] [--include ids] [--exclude ids] [--no-grind] [--no-addons] [--tier\|--ram\|--gpu\|--detect] [--verify] [--write [--force]]` | tags → families → mods.txt proposal | `mods.txt` with `--write` |
| `search <query> [--type mod\|resourcepack\|shader]` | Modrinth search for the pack's game and loader | |
| `info <slug>` | project details and compatible versions | |
| `hardware [--ram GB] [--gpu apple\|nvidia\|amd\|intel] [--apply]` | heap, tier, shaders, perf family | `pack.json` (`memory_mb`, `hardware`), `mods.txt` with `--apply` |
| `build [--server] [--strict] [--out file]` | resolve mods.txt, fetch non-Modrinth jars, enable resource and shader packs by default, write the mrpack; `--server` syncs `server/mods`, `server/config`, `server/defaultconfigs`, `server/kubejs` | `<Name>-<ver>.mrpack`, `build-report.md/.json`, `overrides/mods/*`, `overrides/options.txt` (`resourcePacks:`), `overrides/config/oculus.properties` or `iris.properties` |
| `test [--skip-build] [--accept-eula] [--timeout s] [--java path]` | install the loader server, run it headless until `Done`, triage the log | `server/`, `smoke-test.log`, `smoke-report.json` |
| `triage [--client] [--log f] [--crash f]` | suspect mods from a log or crash report (`--client`: the Prism instance's) | |
| `registry [--mods dir] [--out f]` | index items, blocks, entities, dimensions, item tags, recipes from `server/mods` plus the vanilla and loader jars | `registry.json` |
| `tune init [--namespace ns]` | add KubeJS and Rhino to mods.txt, write a `tune.json` skeleton | `tune.json`, `mods.txt` |
| `tune check [--difficulty d]` | validate `tune.json` against `registry.json`; prints which mod pairs the integrations bridge | (`--difficulty` writes the preset into tune.json) |
| `tune build [--difficulty d]` | check, then write the KubeJS scripts and placeholder icons | `overrides/kubejs/startup_scripts/packloom.items.js`, `server_scripts/packloom.tune.js`, `assets/<ns>/textures/item/*.png` |
| `tune verify` | after a server run: did KubeJS load the scripts, how many recipes changed, any script errors | |
| `tune doc` | the integrations of `tune.json` as a page for players | `INTEGRATIONS.md` |
| `keys [--options f] [--notes keybinds.json] [--apply]` | keyboard map from the instance's `options.txt` | `keybinds.html`; `options.txt` with `--apply` |
| `prism` | locate the Prism instance for this pack | |
| `bundle [client\|server\|both] [--out dir]` | folders for friends (mrpack, docs, keybinds.html) and for a host (mods, configs, kubejs, start.sh) + zips | `dist/` |
| `help-syntax` | print `SYNTAX.md` | |

`--json` on most commands prints machine-readable output for the skills. Exit code 1 means a problem the
output names (missing entry with `--strict`, server did not come up, tune errors, unverified slugs).

## Where things come from

- Mod versions: Modrinth API v2 (`User-Agent: packloom`), FTB maven for `ftb:` lines, direct URLs with hashes.
- Loader versions: Forge promotions, NeoForge and Fabric meta.
- Java: `JAVA_HOME`, Prism's bundled runtimes, `/usr/libexec/java_home`, else a download into the pack folder.
- Vanilla and Forge ids for the registry: `server/libraries/net/minecraft/server/*-extra.jar` and
  `net/minecraftforge/forge/*-universal.jar`, so `minecraft:` items and `#forge:` tags are known.
