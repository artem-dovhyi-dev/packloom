"""The catalog: families of mods that do one job, with tags, cost and grind. `design` turns a wish list of
tags into a mods.txt proposal; `verify` checks every slug against Modrinth for the pack's game and loader."""
from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import modrinth
from .manifest import parse_mods

CATALOG_DIR = Path(__file__).resolve().parents[2] / "catalog"
GRIND = ("low", "medium", "high")
WEIGHT = ("light", "medium", "heavy")
TIERS = ("low", "mid", "high")
TIER_MAX_WEIGHT = {"low": "light", "mid": "medium", "high": "heavy"}


def load(path: Optional[Path] = None) -> dict:
    path = path or CATALOG_DIR / "families.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for fam in data["families"]:
        for k in ("grind", "weight"):
            if fam.get(k, "low") not in (GRIND if k == "grind" else WEIGHT):
                raise ValueError(f"family {fam['id']}: bad {k} {fam[k]!r}")
    return data


def key(minecraft: str, loader: str) -> str:
    return f"{minecraft}/{loader.lower()}"


def family_lines(fam: dict, minecraft: str, loader: str, with_addons: bool = True) -> list[str]:
    """mods.txt lines for a family on this game and loader; [] when the family has nothing for it."""
    k = key(minecraft, loader)
    lines = list(fam.get("mods", {}).get(k, []))
    if lines and with_addons:
        for slug, why in fam.get("addons", {}).get(k, []):
            lines.append(f"{slug}   # {why}")
    return lines


@dataclass
class Pick:
    family: dict
    reasons: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Proposal:
    minecraft: str
    loader: str
    picks: list[Pick]
    skipped: list[tuple[str, str]]   # (family id, why)
    available: list[tuple[str, str, str]] = field(default_factory=list)   # (family id, title, matched tags): extras not picked

    def mods_txt(self, name: str = "") -> str:
        out = [f"# {name or 'pack'}: written by `packloom design` for Minecraft {self.minecraft} {self.loader}.",
               "# One entry per line, `#` starts a comment. Required dependencies come from Modrinth automatically.", ""]
        for p in self.picks:
            out.append(f"# --- {p.family['title']}: {p.family['summary']} ---")
            out += p.lines
            out.append("")
        return "\n".join(out)

    def as_dict(self) -> dict:
        return {"minecraft": self.minecraft, "loader": self.loader,
                "families": [{"id": p.family["id"], "title": p.family["title"], "reasons": p.reasons,
                              "warnings": p.warnings, "lines": p.lines} for p in self.picks],
                "skipped": [{"id": i, "why": w} for i, w in self.skipped],
                "available": [{"id": i, "title": t, "tags": g} for i, t, g in self.available]}


def design(catalog: dict, minecraft: str, loader: str, want: list[str], avoid: list[str] = (),
           tier: str = "high", include: list[str] = (), exclude: list[str] = (), addons: bool = True,
           no_grind: bool = False) -> Proposal:
    """Pick families: every `default` family, every `core` family that matches a wanted tag, plus `include`;
    drop `avoid` tags, `exclude` ids, families too heavy for the hardware tier, and the losers of each
    exclusive `group` (highest priority wins). `no_grind` drops grind=high families unless included by id.
    Families marked `"pick": "extra"` (the second Aether, the fifth magic mod) are never picked by a tag: the
    catalog knows them so a person can ask for one by name (`--include`); they are listed as `available`."""
    want, avoid = set(want), set(avoid)
    unknown = (want | avoid) - set(catalog["tags"])
    if unknown:
        raise ValueError(f"unknown tags: {', '.join(sorted(unknown))}; known: {', '.join(catalog['tags'])}")
    max_w = WEIGHT.index(TIER_MAX_WEIGHT.get(tier, "heavy"))
    picks: list[Pick] = []
    skipped: list[tuple[str, str]] = []
    available: list[tuple[str, str, str]] = []
    for fam in catalog["families"]:
        fid = fam["id"]
        lines = family_lines(fam, minecraft, loader, addons)
        forced = fid in include
        if fid in exclude:
            skipped.append((fid, "excluded")); continue
        if not lines:
            if forced or (want & set(fam["tags"])):
                skipped.append((fid, f"nothing for {key(minecraft, loader)} in the catalog"))
            continue
        matched = want & set(fam["tags"])
        if not (forced or matched or fam.get("default")):
            continue
        if fam.get("pick", "core") == "extra" and not forced:
            if not (avoid & set(fam["tags"])):
                available.append((fid, fam["title"], ", ".join(sorted(matched))))
            continue
        if avoid & set(fam["tags"]) and not forced:
            skipped.append((fid, f"avoids {', '.join(sorted(avoid & set(fam['tags'])))}")); continue
        if WEIGHT.index(fam.get("weight", "light")) > max_w and not forced:
            skipped.append((fid, f"{fam['weight']} for a {tier}-tier machine")); continue
        if no_grind and fam.get("grind") == "high" and not forced:
            skipped.append((fid, "grind=high and --no-grind; pass --include to keep it")); continue
        p = Pick(fam, lines=lines)
        if forced:
            p.reasons.append("asked for by id")
        if matched:
            p.reasons.append("wants " + ", ".join(sorted(matched)))
        if fam.get("default") and not matched:
            p.reasons.append("default for every pack")
        if fam.get("grind") == "high":
            p.warnings.append("grindy by default" + (f": {fam['tune_hint']}" if fam.get("tune_hint") else ""))
        if fam.get("weight") == "heavy":
            p.warnings.append("heavy on the client")
        picks.append(p)
    # exclusive groups: keep the highest priority, say why the others went
    by_group: dict[str, list[Pick]] = {}
    for p in picks:
        if p.family.get("group"):
            by_group.setdefault(p.family["group"], []).append(p)
    for group, members in by_group.items():
        members.sort(key=lambda p: (p.family["id"] in include, p.family.get("priority", 0)), reverse=True)
        for loser in members[1:]:
            picks.remove(loser)
            skipped.append((loser.family["id"], f"same job as {members[0].family['id']} ({group}); pass --include {loser.family['id']} to swap"))
    picks.sort(key=lambda p: -p.family.get("priority", 0))
    return Proposal(minecraft, loader, picks, skipped, available)


def verify(lines: list[str], minecraft: str, loader: str, log=print) -> list[tuple[str, str]]:
    """Ask Modrinth whether every slug in these mods.txt lines has a version for the game and loader.
    ftb:, url: and manual: entries are not Modrinth and are skipped. Returns (ref, problem) pairs."""
    problems = []
    for e in parse_mods("\n".join(lines)):
        if e.source != "modrinth":
            continue
        proj = modrinth.project(e.ref)
        if not proj:
            problems.append((e.ref, "not on Modrinth")); log(f"  {e.ref}: NOT FOUND"); continue
        found = modrinth.versions(proj["id"], minecraft, loader, proj["project_type"])
        if not found:
            problems.append((e.ref, f"no version for {minecraft} {loader}")); log(f"  {e.ref}: no {minecraft} {loader} version")
        else:
            log(f"  {e.ref}: {found[0]['version_number']}")
    return problems


def all_lines(catalog: dict, minecraft: str, loader: str) -> list[str]:
    seen, out = set(), []
    for fam in catalog["families"]:
        for line in family_lines(fam, minecraft, loader):
            ref = line.split()[0]
            if ref not in seen:
                seen.add(ref); out.append(line)
    return out


def find_family(catalog: dict, pattern: str) -> list[dict]:
    return [f for f in catalog["families"] if fnmatch.fnmatch(f["id"], pattern) or pattern.lower() in f["title"].lower()]
