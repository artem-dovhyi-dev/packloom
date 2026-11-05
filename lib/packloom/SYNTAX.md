# pack.json

```json
{ "name": "TechPack", "version": "1.0.0", "minecraft": "1.20.1", "loader": "forge",
  "loader_version": "recommended", "memory_mb": 6144 }
```

`loader`: forge | neoforge | fabric | quilt. `loader_version`: `recommended`, `latest` or an exact version.
`memory_mb` sizes the server smoke test and is the suggested client allocation.

# mods.txt

One entry per line. `#` starts a comment; blank lines and `# --- headings ---` are ignored.

| Line | Meaning |
|---|---|
| `slug` | Modrinth project, newest stable version for the pack's game and loader |
| `slug@1.4.18` | pinned Modrinth `version_number`; the build fails if it does not exist |
| `slug client` / `slug server` | force the side; otherwise the client is always required and the server follows Modrinth's `server_side` |
| `ftb:ftb-quests-forge` | artifact from the FTB maven, newest non-snapshot for the game branch; shipped in `overrides/mods` |
| `url:https://host/mod.jar sha256=…` | direct jar into `overrides/mods`; the hash is optional |
| `manual:flux-networks  # CurseForge` | not downloaded; listed in the build report as a manual step |

Required dependencies are resolved from Modrinth automatically, so libraries need no line of their own.
A resource pack or shader pack slug (`faithful-32x`, `complementary-reimagined`) goes into `resourcepacks/` or
`shaderpacks/` of the mrpack and is enabled by default: `build` writes the `resourcePacks:` line of
`overrides/options.txt` and `shaderPack=` in `overrides/config/oculus.properties` (`iris.properties` on Fabric).

`hardware` (written by `packloom hardware --apply`): `{ "ram_gb": 16, "gpu": "apple", "tier": "mid" }`.
`memory_mb` then follows the machine: ~40 % of RAM between 3 and 10 GB.

# tune.json

Recipes, pack-only items, integrations between mods and difficulty presets as data; `packloom tune build`
checks every id against `registry.json` and writes the KubeJS scripts into `overrides/kubejs/`; `tune doc`
writes `INTEGRATIONS.md`. Full reference: `docs/tune.md`, `docs/integrations.md`.

```json
{ "namespace": "mypack", "difficulty": "normal",
  "integrations": [{ "id": "a-b", "title": "A meets B", "bridges": ["moda", "modb"], "tier": "mid", "why": "...",
                     "items": [], "recipes": [], "remove": [], "replace_inputs": [] }],
  "items": [{ "id": "mypack:blade", "name": "Blade", "type": "sword", "tier": "netherite", "attack_damage_bonus": 4 }],
  "recipes": [{ "type": "shaped", "pattern": ["A", "B"], "key": {"A": "mod:sword", "B": "mod:core"}, "result": "mypack:blade" }],
  "remove": [{ "output": "mod:item" }],
  "replace_inputs": [{ "in": {"output": "mod:machine"}, "from": "#forge:ingots/iron", "to": "#forge:ingots/gold" }],
  "presets": { "easy": { "replace_inputs": [] }, "hard": { "replace_inputs": [] } } }
```
