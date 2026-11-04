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
