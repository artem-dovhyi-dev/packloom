"""Turn a server log or crash report into a list of suspect mods with evidence.
Heuristics only; when nothing matches, `suspects` is empty and says so."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

IGNORED_PACKAGES = ("java.", "jdk.", "sun.", "net.minecraft.", "net.minecraftforge.", "net.neoforged.",
                    "cpw.mods.", "org.spongepowered.", "org.objectweb.", "com.mojang.", "io.netty.",
                    "com.google.", "org.apache.", "it.unimi.", "org.lwjgl.", "javax.", "kotlin.")


@dataclass
class Suspect:
    mod: str
    kind: str          # mixin | missing-dependency | stacktrace | duplicate | version
    evidence: str
    action: str = ""   # remove | pin | add-dependency | config | investigate


@dataclass
class Triage:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: int = 0
    missing_deps: list[str] = field(default_factory=list)
    suspects: list[Suspect] = field(default_factory=list)
    mods_loaded: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


def _add(suspects: list[Suspect], mod: str, kind: str, evidence: str, action: str) -> None:
    if not any(s.mod == mod and s.kind == kind for s in suspects):
        suspects.append(Suspect(mod, kind, evidence.strip()[:300], action))


CLIENT_OK = ("Sound engine started", "OpenAL initialized", "Narrator library")


def analyze(lines: list[str], crash_text: Optional[str] = None, mod_ids: Optional[set] = None, client: bool = False) -> Triage:
    mod_ids = set(mod_ids or ())
    if client:
        ok = any(any(m in l for m in CLIENT_OK) for l in lines) and not crash_text
    else:
        ok = any("Done (" in l and "For help" in l for l in lines)
    t = Triage(ok=ok)
    t.errors = [l.strip() for l in lines if re.search(r"/(ERROR|FATAL)\]", l)]
    t.warnings = sum(1 for l in lines if re.search(r"/WARN\]", l) and "Mod file" not in l)
    t.mods_loaded = next((m.group(0) for l in lines for m in [re.search(r"Loading \d+ mods?:|\d+ mods? loaded", l)] if m), "")
    joined = "\n".join(lines) + "\n" + (crash_text or "")

    for m in re.finditer(r"Mixin apply for mod (\S+?) failed|Mixin config (\S+?)\.mixins\.json", joined):
        mod = m.group(1) or m.group(2)
        _add(t.suspects, mod, "mixin", m.group(0), "remove")
    for m in re.finditer(r"Mixin apply failed (\S+?)\.mixins\.json", joined):
        _add(t.suspects, m.group(1), "mixin", m.group(0), "remove")

    for m in re.finditer(r"Mod ID: '([^']+)', Requested by: '([^']+)', Expected range: '([^']*)'(?:, Actual version: '([^']*)')?", joined):
        mod, by, rng, actual = m.groups()
        t.missing_deps.append(f"{by} needs {mod} {rng}" + (f" (has {actual})" if actual else ""))
        _add(t.suspects, by, "missing-dependency", m.group(0), "add-dependency" if actual in (None, "[MISSING]") else "pin")

    for m in re.finditer(r"Duplicate mods? found[^\n]*?Mod ID: '([^']+)'[^\n]*", joined):
        _add(t.suspects, m.group(1), "duplicate", m.group(0), "remove")

    for m in re.finditer(r"^.*(?:packloom\.\w+\.js|KubeJS).*(?:Error|Exception|ERROR).*$", joined, re.M):
        if "packloom" in m.group(0) or "server_scripts" in m.group(0) or "startup_scripts" in m.group(0):
            _add(t.suspects, "kubejs-script", "script", m.group(0), "config")   # fix tune.json, then `tune build`
    if crash_text:
        _stacktrace_suspects(crash_text, mod_ids, t.suspects)
    if not t.ok and not t.suspects:
        first = next((l for l in lines if re.search(r"/(ERROR|FATAL)\]", l)), "")
        if first:
            _add(t.suspects, "?", "stacktrace", first, "investigate")
    return t


def crash_mod_list(crash_text: str) -> dict[str, str]:
    """Crash report 'Mod List' table: file name -> mod id."""
    out = {}
    for m in re.finditer(r"^\s*\|\s*(\S+\.jar)\s*\|[^|]*\|\s*([a-z0-9_]+)\s*\|", crash_text, re.M):
        out[m.group(1)] = m.group(2)
    return out


def _stacktrace_suspects(crash_text: str, mod_ids: set, suspects: list[Suspect]) -> None:
    ids = set(mod_ids) | set(crash_mod_list(crash_text).values())
    seen = []
    for m in re.finditer(r"^\s*at ([a-zA-Z0-9_.$]+)\(", crash_text, re.M):
        pkg = m.group(1)
        if pkg.startswith(IGNORED_PACKAGES):
            continue
        parts = pkg.split(".")
        candidates = [p for p in parts if p in ids]
        mod = candidates[0] if candidates else next((p for p in parts[1:4] if len(p) > 3), parts[0])
        if mod not in seen:
            seen.append(mod)
            _add(suspects, mod, "stacktrace", m.group(0), "investigate" if not candidates else "remove")
        if len(seen) >= 3:
            break
