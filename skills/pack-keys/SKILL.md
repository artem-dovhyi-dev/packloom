---
name: pack-keys
description: Render an interactive HTML keyboard map of every keybind in a Minecraft instance from options.txt, grouped by mod, with conflicts highlighted. Use when the user asks which key does what, complains about overlapping or conflicting keybinds, or wants a cheat sheet of controls for a modpack.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read
---

# Keyboard map

From the Prism instance matching the pack (reads `minecraft/options.txt`):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> keys --json
```

From any file: `keys --options <path/to/options.txt> --out <file.html>`.

Output: `keybinds.html` next to `pack.json` (open it in a browser: hover a key for its actions and mods, click a
mod to highlight its keys, search by action) and a JSON summary with per-mod counts and conflicts.

Mod keybinds appear in `options.txt` only after the game has been launched once with those mods, so a fresh
instance shows vanilla keys only. Say so if the count looks vanilla-sized.

The mod name is inferred from the keybind id (`key.sophisticatedbackpacks.open_backpack` → sophisticatedbackpacks);
ids without a namespace land under a guessed name. When asked to fix conflicts, propose new keys and explain the
grouping (for example: all "open GUI" keys on one row), then edit `options.txt` lines `key_<id>:key.keyboard.<key>`
only with the game closed, since Minecraft rewrites the file on exit.
