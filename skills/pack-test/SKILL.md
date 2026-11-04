---
name: pack-test
description: Smoke-test a Minecraft modpack by installing its loader server under <pack>/server and starting it headless until "Done" or a crash. Produces smoke-report.json with errors, missing dependencies and suspect mods. Use after every build, when the user asks whether the pack works, or before sharing it.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *)
---

# Smoke test on a headless server

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> test --json
```

The command rebuilds the pack with `--server`, finds Java of the right major version (packloom cache,
`java_home`, Prism's runtime, then a Temurin download from the Adoptium API; no sudo), installs the Forge/NeoForge
server with its official installer if `server/run.sh` is missing, starts it with `nogui`, waits up to 15 minutes
for `Done (…)` and sends `stop`. Output: `smoke-test.log`, `smoke-report.json`, exit 0 on success.

**EULA.** The first run fails with "eula.txt lacks eula=true". Accepting Minecraft's EULA is the user's decision:
ask once, then rerun with `--accept-eula`. If the user has already said yes in this conversation, pass the flag.

Reading the report:
- `ok: true` means every mod loaded and the world generated. Warnings are normal in modded packs; mention the count only.
- `missing_deps` names the mod that asked and what it needs. Add the dependency to `mods.txt` or pin a matching version.
- `suspects` lists mods with evidence and a suggested action (`remove`, `pin`, `add-dependency`, `config`, `investigate`).
  Treat them as leads, not verdicts: a mixin failure in mod A is often caused by mod B being the wrong version.
- `crash_report` is the full crash file; read it when suspects are empty or marked `investigate`.

Options: `--skip-build` reuses the last build, `--timeout <s>`, `--java <path>`, `--no-download-java`.
A server test does not exercise rendering, shaders or client-only mods; those need a client launch (see `/pack-triage --client`).
