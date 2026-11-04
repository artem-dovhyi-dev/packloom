---
name: pack-add
description: Find a Minecraft mod on Modrinth for the pack's game version and loader, inspect its versions and required dependencies, and add it to mods.txt. Use when the user asks to add, find, look up or replace a mod, or asks whether a mod exists for their Minecraft version.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Edit
---

# Find and add a mod

Search (filtered to the pack's game version and loader):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> search "<query>" --limit 8
```

Inspect one project (compatible versions, side support, required dependencies):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> info <slug>
```

Then edit `mods.txt`: add the slug on its own line under the fitting `# --- section ---`, with a short trailing
comment on why it is in the pack. Required dependencies resolve automatically; do not add libraries by hand
unless Modrinth fails to mark them as required (then add them with a comment saying so).

Syntax reminders: `slug@version` pins, `slug client` keeps a rendering mod off the server,
`ftb:<artifact>` for FTB maven, `url:<jar>` for direct downloads, `manual:<name>` for CurseForge-only mods.

Prefer the mod with the most downloads among equivalents, but say when a smaller one fits the pack's loader
or version better. When `search` returns nothing, try the mod's common alternative names, then tell the user
it is not on Modrinth and offer `manual:`.

Finish with `/pack-build` so the user sees the resolved versions and any missing entries.
