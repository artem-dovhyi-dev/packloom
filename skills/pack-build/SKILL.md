---
name: pack-build
description: Build a Minecraft modpack from mods.txt and pack.json into an .mrpack for Prism Launcher. Resolves Modrinth projects and their required dependencies, fetches FTB-maven and direct-URL jars into overrides/mods, writes build-report.md. Use when the user adds or removes mods, changes versions, or asks to rebuild, export or package the pack.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *)
---

# Build the pack

Run from the folder that holds `pack.json`, or pass `--pack <dir>`:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> build --json
```

What it does, in order: parse `mods.txt`, resolve every Modrinth entry and its required dependencies for the
pack's game and loader, download `ftb:` and `url:` entries into `overrides/mods`, look up the loader version,
write `<name>-<version>.mrpack` (index of download links plus `overrides/`), `build-report.md` and `build-report.json`.

Read the report before answering. Three sections matter:
- **Not found**: a slug is wrong or has no version for this game/loader. Use `/pack-add` to search for the right slug,
  or pin a version. Do not silently drop the mod; tell the user.
- **Manual install**: `manual:` entries (usually CurseForge-only). Repeat the note to the user.
- **Shipped in overrides/mods**: jars that bypass Modrinth. These are inside the mrpack itself.

`--server` also syncs `server/mods` (every server-side jar). `--strict` returns exit 1 on any missing entry.
`mods.txt` syntax: `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py help-syntax`.

After a successful build, the user imports the mrpack in Prism (Add Instance → Import). An existing instance
needs to be updated or re-imported; Prism does not watch the file.
