# packloom

**Describe a Minecraft modpack in words, get one that starts.**

packloom is a [Claude Code](https://claude.com/claude-code) plugin and a plain Python CLI that turns a modpack
into text you can edit, build and verify with an agent: a wish list of tags becomes a mod list from a curated
catalog, Modrinth resolves versions and dependencies, a headless server proves the pack loads, recipes and
difficulty presets are data that are checked against the real item registry before any script is written.
No launcher of its own: it exports an `.mrpack` that Prism Launcher imports.

```
"RPG + industry, some farming, a pretty world, not much grind, runs on my M1 laptop"
        │
        ▼ /pack-design (catalog of families, verified on Modrinth)
mods.txt + pack.json ──/pack-build──▶ TechPack-1.2.0.mrpack ──▶ Prism Launcher
        ▲                                      │
        │  tune.json ──/pack-tune──▶ KubeJS    │ /pack-test (headless Forge server, KubeJS included)
        │                                      ▼
        └──────── /pack-triage ◀── smoke-report.json, crash reports, script errors
```

**Status: 0.2, built for one pack first** (TechPack: 1.20.1 Forge, 85 files, DivineRPG next to Thermal,
Mekanism, AE2, bees, Farmer's Delight, Biomes O' Plenty). The catalog covers 1.20.1 Forge well and 1.20.1
Fabric partly; every slug in it is verified against Modrinth by `catalog verify`.

▶ **[Watch the terminal demo](docs/demo.md)** (half a minute, idle time compressed): design → hardware → tune → test → keys.

## Why

Assembling a modpack is mostly bookkeeping: which versions exist for this game and loader, which libraries they
drag in, which two mods explode together at load time, which item id a recipe should use. The bookkeeping is
text and the explosions are in logs, so an agent that reads files and runs a server does the loop better than a
human clicking through a launcher. The parts that are taste (what is fun) stay with the human: packloom
proposes, the human decides.

## The five things it does

| You say | Skill | What happens |
|---|---|---|
| "I want RPG and industry, farming, a nice world, no grind, with friends" | `/pack-design` | tags → families from the catalog → `mods.txt`, every slug verified on Modrinth for your game and loader; same-job families (Thermal vs Create) are picked by priority and the swap is one flag |
| "Make it harder" / "the quarry should need a diamond block" / "a sword that combines DivineRPG and Thermal" | `/pack-tune` | `tune.json` holds items, recipes, removals, input swaps and `easy`/`normal`/`hard` presets; every id is checked against the registry (16 000 recipes, 8 800 items in TechPack) with "did you mean" hints; KubeJS scripts are generated, never hand-written |
| "It has to run on my 16 GB M1" / "my friend has 8 GB" | `/pack-hardware` | heap, tier, shader preset, mod ceiling, Apple Silicon notes; `--apply` writes `memory_mb` and adds the performance family |
| "Which key does what? B is taken twice" | `/pack-keys` | an interactive keyboard page from `options.txt`, conflicts in red, per-stage filters; `--apply` writes a layout back |
| "Does it even start?" | `/pack-build`, `/pack-test`, `/pack-triage` | mrpack with hashes, headless server with the right Java, crash log → suspect mods, KubeJS script errors as suspects too |

Details and real output for each: [docs/use-cases.md](docs/use-cases.md).

## Quick start

```bash
git clone https://github.com/artem-dovhyi-dev/packloom && cd packloom
alias packloom='PYTHONPATH=$PWD/lib python3 -m packloom'

mkdir ../mypack && cd ../mypack
packloom init --name MyPack --minecraft 1.20.1 --loader forge
packloom design --want tech,rpg,farming,worldgen,coop --no-grind --include divinerpg --detect --verify --write
packloom hardware --apply
packloom build --server
packloom test --accept-eula          # Minecraft EULA: a human decision, hence the flag
packloom tune init --namespace mypack && packloom registry && packloom tune build
packloom build --server && packloom test --skip-build && packloom tune verify
packloom bundle                      # dist/MyPack-0.1.0-client and -server folders + zips
```

Then Prism Launcher → Add Instance → Import → the `.mrpack`. Full walk-through: [docs/tutorial.md](docs/tutorial.md).

Python 3.9+, standard library only. Java for the server test is found or downloaded by `test` (no sudo).

## Install as a Claude Code plugin

In a project that holds a pack, add to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "packloom": { "source": { "source": "github", "repo": "artem-dovhyi-dev/packloom", "ref": "main" } }
  },
  "enabledPlugins": { "packloom@packloom": true }
}
```

You get `/pack-init`, `/pack-design`, `/pack-add`, `/pack-build`, `/pack-test`, `/pack-triage`, `/pack-tune`,
`/pack-hardware`, `/pack-keys`. For hacking on the plugin itself: `claude --plugin-dir /path/to/packloom`.

## The pack format

```
mypack/
  pack.json      { "name": "TechPack", "version": "1.2.0", "minecraft": "1.20.1", "loader": "forge",
                   "loader_version": "recommended", "memory_mb": 6144, "hardware": {"ram_gb": 16, "gpu": "apple", "tier": "mid"} }
  mods.txt       one entry per line, comments with #
  tune.json      items, recipes, presets -> overrides/kubejs (generated)
  overrides/     config/, defaultconfigs/, kubejs/, options.txt, mods/ for jars that are not on Modrinth
  registry.json  generated index of every item, tag, recipe in the jars
```

`mods.txt` lines:

```
thermal-expansion                 # a Modrinth slug: newest stable for the pack's game and loader
mekanism@10.4.16.80               # pinned version
embeddium client                  # keep a rendering mod off the server
ftb:ftb-quests-forge              # FTB maven artifact, shipped in overrides/mods
url:https://example.com/x.jar sha256=…
manual:flux-networks              # CurseForge-only: listed as a manual step in the report
```

Required dependencies come from Modrinth automatically. Full syntax: `lib/packloom/SYNTAX.md`.

## Documentation

- [docs/use-cases.md](docs/use-cases.md): the five use cases with real commands and output
- [docs/tutorial.md](docs/tutorial.md): from an empty folder to friends playing
- [docs/commands.md](docs/commands.md): every CLI command and flag
- [docs/tune.md](docs/tune.md): `tune.json` reference and how difficulty presets work
- [docs/catalog.md](docs/catalog.md): the catalog format and how to add a family
- [docs/demo.md](docs/demo.md): the recorded terminal session
- [docs/README.uk.md](docs/README.uk.md): короткий посібник українською

## Keybinds as data

`keybinds.json` next to the pack holds the layout, game stages and per-key notes; `packloom keys` renders
`keybinds.html` (hover a key, click a mod, filter by stage) and `keys --apply` writes the layout into the
instance. ![keyboard map](docs/keybinds.jpg)

## What it will not do

Download from CurseForge (their API needs a key and some authors forbid it; such mods are `manual:` lines),
run the game client (Prism does that), or decide what is fun. The catalog is an opinion: one family per job,
few add-ons, no grind by default.

## Development

```bash
python3 -m unittest discover -s tests          # 28 tests, stdlib unittest
PYTHONPATH=lib python3 -m packloom --help
```

Built with Claude Code; the design decisions, the catalog's opinions and the pack it was built for are the
author's. MIT.
