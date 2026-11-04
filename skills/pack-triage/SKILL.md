---
name: pack-triage
description: Diagnose a Minecraft modpack crash or failed start from a server log, a crash report, or the Prism Launcher client logs. Maps mixin errors, missing dependencies and stack traces to suspect mods with suggested actions. Use when the game or server crashes, when the user pastes a crash report, or after a failed pack-test.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Grep
---

# Triage a crash

Server side (default: `smoke-test.log` and the newest `server/crash-reports/*.txt`):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> triage
```

Client side, from the Prism instance that matches the pack's name (`minecraft/logs/latest.log` and the newest crash report):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py --pack <dir> triage --client
```

Explicit files: `--log <path>`, `--crash <path>`.

The output is JSON: `errors` (first 30 ERROR/FATAL lines), `missing_deps`, `suspects` with `kind`
(mixin, missing-dependency, duplicate, stacktrace), `evidence` and `action`.

How to act on it:
1. `missing-dependency` → add the dependency slug to `mods.txt`, or pin the requesting mod to a version that fits. Rebuild and test.
2. `mixin` → usually a version mismatch between two mods, or a client-only mod on the server. Check `build-report.md`
   for the versions involved, then pin or mark `client`.
3. `duplicate` → two jars provide the same mod id; one is often in `overrides/mods` and one from Modrinth. Remove one.
4. `stacktrace` with `investigate` → read the crash report around the first non-Minecraft frame; the heuristics could not name a mod.

Propose the change and the reason. Edit `mods.txt` yourself only when the user has asked you to fix things
autonomously; otherwise show the diff and wait. After any change: `/pack-build` then `/pack-test`.
