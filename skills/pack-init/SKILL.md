---
name: pack-init
description: Start a new Minecraft modpack folder for packloom, with pack.json (name, version, Minecraft version, loader, memory) and an empty mods.txt. Use when the user wants to create a new modpack from scratch or convert an existing mod list into a packloom pack.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *)
---

# Start a pack

Ask for (or infer from the conversation) the name, Minecraft version and loader; default memory 4096 MB,
version 0.1.0. Then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py init --dir <dir> --name <Name> --minecraft 1.20.1 --loader forge --memory 6144
```

This writes `pack.json`, a commented `mods.txt` and an empty `overrides/` (configs, datapacks, options.txt
and `mods/` for non-Modrinth jars all go there and are copied into every instance as-is).

If the user already has a list of mods, write them into `mods.txt` one slug per line grouped under
`# --- sections ---`, then run `/pack-build` to see which slugs resolve.

Loader choice when the user has none: Fabric for the newest Minecraft, NeoForge for 1.20.5+ "big tech" packs,
Forge for 1.20.1 where most large packs and quest mods still live.
