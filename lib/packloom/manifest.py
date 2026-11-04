"""pack.json and mods.txt: the two files that describe a modpack."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SOURCES = ("modrinth", "ftb", "url", "manual")
SIDES = ("client", "server", "both")


@dataclass
class ModEntry:
    source: str                 # modrinth | ftb | url | manual
    ref: str                    # slug, ftb artifact, url, or a name for manual entries
    version: Optional[str] = None   # pinned Modrinth version_number
    side: Optional[str] = None      # client | server | both | None (ask Modrinth)
    sha256: Optional[str] = None
    comment: str = ""
    line_no: int = 0

    @property
    def key(self) -> str:
        return f"{self.source}:{self.ref}"


def parse_mods(text: str) -> list[ModEntry]:
    """One entry per line. `#` starts a comment. Blank lines and headings are skipped.

    Grammar (see .scratch/packloom/issues/06-pack-manifest-syntax.md):
      slug | slug@1.2.3 | slug client | ftb:artifact | url:https://x/y.jar sha256=... | manual:name
    """
    entries: list[ModEntry] = []
    for no, raw in enumerate(text.splitlines(), 1):
        body, _, comment = raw.partition("#")
        tokens = body.split()
        if not tokens:
            continue
        head, *rest = tokens
        source, ref, version = "modrinth", head, None
        m = re.match(r"^(ftb|url|manual):(.+)$", head)
        if m:
            source, ref = m.group(1), m.group(2)
        elif "@" in head:
            ref, version = head.split("@", 1)
        entry = ModEntry(source=source, ref=ref, version=version, comment=comment.strip(), line_no=no)
        for tok in rest:
            if tok in SIDES:
                entry.side = tok
            elif tok.startswith("sha256="):
                entry.sha256 = tok[len("sha256="):].lower()
            else:
                raise ValueError(f"mods.txt line {no}: unknown token {tok!r}")
        if not re.match(r"^[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$", ref):
            raise ValueError(f"mods.txt line {no}: bad reference {ref!r}")
        entries.append(entry)
    return entries


@dataclass
class Pack:
    dir: Path
    name: str
    version: str
    minecraft: str
    loader: str                      # forge | neoforge | fabric | quilt
    loader_version: str = "recommended"
    memory_mb: int = 4096
    extra: dict = field(default_factory=dict)

    @property
    def mods_file(self) -> Path:
        return self.dir / "mods.txt"

    @property
    def overrides(self) -> Path:
        return self.dir / "overrides"

    @property
    def server_dir(self) -> Path:
        return self.dir / "server"

    @property
    def mrpack_path(self) -> Path:
        return self.dir / f"{self.name}-{self.version}.mrpack"

    def entries(self) -> list[ModEntry]:
        return parse_mods(self.mods_file.read_text(encoding="utf-8"))

    @property
    def java_major(self) -> int:
        return java_major_for(self.minecraft)


REQUIRED = ("name", "version", "minecraft", "loader")


def load_pack(path: Path) -> Pack:
    path = Path(path).resolve()
    if path.is_dir():
        path = path / "pack.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")
    known = {k: data[k] for k in ("loader_version", "memory_mb") if k in data}
    extra = {k: v for k, v in data.items() if k not in REQUIRED and k not in known}
    return Pack(dir=path.parent, name=data["name"], version=str(data["version"]),
                minecraft=data["minecraft"], loader=data["loader"].lower(), extra=extra, **known)


def find_pack_dir(start: Path) -> Optional[Path]:
    """`start` itself, then any direct child, then the parents, first one holding pack.json wins."""
    start = Path(start).resolve()
    candidates = [start, *sorted(p for p in start.iterdir() if p.is_dir())] if start.is_dir() else []
    candidates += list(start.parents)
    for c in candidates:
        if (c / "pack.json").is_file():
            return c
    return None


def java_major_for(minecraft: str) -> int:
    parts = [int(x) for x in re.findall(r"\d+", minecraft)[:3]] + [0, 0]
    major, minor, patch = parts[0], parts[1], parts[2]
    if (major, minor) < (1, 17):
        return 8
    if (major, minor) == (1, 17):
        return 16
    if (major, minor, patch) < (1, 20, 5):
        return 17
    return 21


def write_pack(pack: Pack) -> None:
    data = {"name": pack.name, "version": pack.version, "minecraft": pack.minecraft, "loader": pack.loader,
            "loader_version": pack.loader_version, "memory_mb": pack.memory_mb, **pack.extra}
    (pack.dir / "pack.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
