"""Mods that do not live on Modrinth: FTB maven artifacts and direct URLs. They go into overrides/mods
because the mrpack format only allows downloads from Modrinth, GitHub and GitLab."""
from __future__ import annotations

import re
from pathlib import Path

from .http import download, get_text
from .manifest import ModEntry, Pack

FTB_MAVEN = "https://maven.ftb.dev/releases/dev/ftb/mods"


def ftb_branch(game: str) -> str:
    """1.20.1 -> 2001, 1.21 -> 2100 (FTB encodes the game version as <minor><patch:02>)."""
    nums = [int(x) for x in re.findall(r"\d+", game)] + [0, 0]
    return f"{nums[1]}{nums[2]:02d}"


def ftb_latest(artifact: str, game: str) -> str:
    xml = get_text(f"{FTB_MAVEN}/{artifact}/maven-metadata.xml")
    branch = ftb_branch(game)
    good = [v for v in re.findall(r"<version>([^<]+)</version>", xml)
            if v.startswith(branch + ".") and "SNAPSHOT" not in v]
    if not good:
        raise RuntimeError(f"ftb maven has no {artifact} for {game} (branch {branch})")
    return max(good, key=lambda v: [int(x) for x in re.findall(r"\d+", v)])


def fetch_overrides(pack: Pack, entries: list[ModEntry], log=print) -> list[tuple[ModEntry, Path]]:
    """Download ftb:/url: entries into overrides/mods, replacing older versions of the same artifact."""
    mods = pack.overrides / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    out = []
    for e in entries:
        if e.source == "ftb":
            v = ftb_latest(e.ref, pack.minecraft)
            name = f"{e.ref}-{v}.jar"
            for old in mods.glob(f"{e.ref}-*.jar"):
                if old.name != name:
                    old.unlink()
            dest = mods / name
            if not dest.exists():
                download(f"{FTB_MAVEN}/{e.ref}/{v}/{name}", dest)
            log(f"  {e.ref:36} {v:28} [ftb maven]")
            out.append((e, dest))
        elif e.source == "url":
            name = e.ref.rsplit("/", 1)[-1].split("?")[0] or "mod.jar"
            dest = mods / name
            if not dest.exists():
                download(e.ref, dest, sha256=e.sha256)
            log(f"  {name:36} {'':28} [url]")
            out.append((e, dest))
    return out
