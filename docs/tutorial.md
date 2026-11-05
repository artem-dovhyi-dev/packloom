# From an empty folder to friends playing

Everything below is one terminal, ten minutes of typing and about fifteen of downloads. Replace `packloom`
with `PYTHONPATH=/path/to/packloom/lib python3 -m packloom`, or run the same steps as `/pack-*` skills in
Claude Code and let it talk you through the choices.

## 1. Say what you want

```bash
mkdir mypack && cd mypack
packloom init --name MyPack --minecraft 1.20.1 --loader forge
packloom catalog tags
packloom design --want tech,rpg,farming,worldgen,coop --no-grind --include divinerpg --detect
```

Read the proposal. Each family says why it is in; `skipped` says why something is out and which flag flips
it. When it looks right:

```bash
packloom design --want tech,rpg,farming,worldgen,coop --no-grind --include divinerpg --detect --verify --write
packloom hardware --apply
```

`--verify` asks Modrinth for every slug; `hardware --apply` sets the heap for this machine and adds the
performance mods.

## 2. Build and prove it starts

```bash
packloom build --server
packloom test --accept-eula
```

`build` writes `MyPack-0.1.0.mrpack` and `build-report.md` (manual steps, like CurseForge-only mods, are
listed there). `test` installs the Forge server, finds Java 17, starts it headless and stops it at `Done`.
`OK: server came up in 30s` is the line you want. If not, `smoke-report.json` names suspects; fix `mods.txt`
(remove, pin with `slug@version`, add a dependency) and repeat `build --server && test --skip-build`.

## 3. Tune it

```bash
packloom tune init --namespace mypack
packloom registry
```

Edit `tune.json`: a pack-only item, a recipe that joins two mods, input swaps for `easy` and `hard`
([reference](tune.md)). Ids come from `registry.json` (`grep '"thermal:' registry.json | head`). Then:

```bash
packloom tune build
packloom build --server && packloom test --skip-build && packloom tune verify
```

## 4. Play it

Prism Launcher → Add Instance → Import → `MyPack-0.1.0.mrpack`. Launch once, set keys, quit, then:

```bash
packloom keys
open keybinds.html
```

`keybinds.json` (layout, stages, notes) makes the page useful for friends; `keys --apply` writes a layout
back into the instance.

## 5. Ship it

```bash
packloom bundle
```

`dist/MyPack-0.1.0-client/` (mrpack, INSTALL.md, keybinds.html, any `docs/*.md`) and
`dist/MyPack-0.1.0-server/` (mods, config, kubejs, server.properties, `start.sh` that installs Forge on first
run), each also zipped. Friends import the mrpack; one of you runs `start.sh` on a machine with 8 GB spare.

## 6. Change it later

- A new mod: one line in `mods.txt`, then step 2. Existing worlds keep going; new biomes only appear in new chunks.
- Harder: `packloom tune build --difficulty hard`, step 2, copy `kubejs/` to the server, restart.
- Version bump: `version` in `pack.json`; the mrpack name follows.
