---
name: pack-hardware
description: Size a modpack to a machine: Java heap, visual tier, which performance mods to ship, what to skip on 8 GB or Apple Silicon. Use when a user says the game lags, asks how much memory to give it, wants the pack to run on a laptop, or describes their hardware.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read
---

# Fit the pack to the machine

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py hardware                       # detect this machine (macOS, Linux)
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py hardware --ram 8 --gpu intel   # someone else's machine
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py hardware --apply               # write memory_mb + hardware into pack.json, add the perf family to mods.txt
```

Output: tier (low / mid / high), client heap in MB, which shader preset is realistic, a ceiling for the mod
count, and notes (Apple Silicon: no OptiFine, Embeddium + Oculus; low tier: skip textures and shaders).

Rules of thumb the numbers come from: heap is ~40 % of RAM between 3 and 10 GB, because the OS, the GPU
driver and (on a host) the server need the rest and G1 pauses grow with the heap. Tier low is under 12 GB or an
integrated Intel GPU; high needs 32 GB and a discrete GPU; everything else is mid, including every Apple
Silicon Mac. `design --tier low` or `--ram/--gpu` drops heavy families (Create, shaders) from a proposal.

When the game lags on a machine that should cope: `/pack-triage --client` first (a mod may be throwing), then
`spark` (`/spark profiler` in game), then shaders off (F6 with Oculus) before touching the mod list.
