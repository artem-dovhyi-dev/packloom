"""Thin Modrinth v2 client: projects, versions, dependency resolution, search."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .http import get_json
from .manifest import ModEntry

API = "https://api.modrinth.com/v2"
FOLDER = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks", "datapack": "datapacks"}
STABILITY = ("release", "beta", "alpha")


def project(slug_or_id: str) -> Optional[dict]:
    return get_json(f"{API}/project/{slug_or_id}")


def versions(project_id: str, game: str, loader: str, project_type: str) -> list[dict]:
    params = {"game_versions": [game]}
    if project_type == "mod":
        params["loaders"] = [loader]
    found = get_json(f"{API}/project/{project_id}/version", params) or []
    found.sort(key=lambda v: v["date_published"], reverse=True)
    return found


def pick_version(found: list[dict], pinned: Optional[str] = None) -> Optional[dict]:
    """Pinned version_number wins; otherwise the newest release, then beta, then alpha."""
    if pinned:
        return next((v for v in found if v["version_number"] == pinned), None)
    for kind in STABILITY:
        for v in found:
            if v["version_type"] == kind:
                return v
    return found[0] if found else None


def search(query: str, game: str, loader: str, limit: int = 8, project_type: str = "mod") -> list[dict]:
    facets = [[f"versions:{game}"], [f"project_type:{project_type}"]]
    if project_type == "mod":
        facets.append([f"categories:{loader}"])
    data = get_json(f"{API}/search", {"query": query, "facets": facets, "limit": limit}) or {}
    return data.get("hits", [])


def primary_file(version: dict) -> dict:
    files = version["files"]
    return next((f for f in files if f.get("primary")), files[0])


@dataclass
class Resolved:
    entry: Optional[ModEntry]        # None for a transitive dependency
    project: dict
    version: dict
    required_by: list[str] = field(default_factory=list)

    @property
    def folder(self) -> str:
        return FOLDER.get(self.project["project_type"], "mods")


@dataclass
class Resolution:
    resolved: dict[str, Resolved] = field(default_factory=dict)   # project_id -> Resolved
    missing: list[tuple[str, str]] = field(default_factory=list)  # (ref, why)


def resolve(entries: list[ModEntry], game: str, loader: str, log=print) -> Resolution:
    """Breadth-first over required dependencies. Only Modrinth entries take part."""
    res = Resolution()
    queue: list[tuple[Optional[ModEntry], str, Optional[str]]] = [
        (e, e.ref, None) for e in entries if e.source == "modrinth"]
    while queue:
        entry, ref, parent = queue.pop(0)
        proj = project(ref)
        if proj is None:
            res.missing.append((ref, "project not found on Modrinth"))
            continue
        pid = proj["id"]
        if pid in res.resolved:
            if parent:
                res.resolved[pid].required_by.append(parent)
            if entry and res.resolved[pid].entry is None:
                res.resolved[pid].entry = entry
            continue
        found = versions(pid, game, loader, proj["project_type"])
        pinned = entry.version if entry else None
        ver = pick_version(found, pinned)
        if ver is None:
            why = f"no version {pinned!r}" if pinned else f"no version for {game} {loader}"
            if pinned and found:
                why += "; available: " + ", ".join(v["version_number"] for v in found[:5])
            res.missing.append((proj["slug"], why))
            continue
        res.resolved[pid] = Resolved(entry=entry, project=proj, version=ver,
                                     required_by=[parent] if parent else [])
        log(f"  {proj['slug']:36} {ver['version_number']:28} [{ver['version_type']}]"
            + (f"  <- {parent}" if parent else ""))
        for dep in ver.get("dependencies", []):
            if dep.get("dependency_type") == "required" and dep.get("project_id") \
                    and dep["project_id"] not in res.resolved:
                queue.append((None, dep["project_id"], proj["slug"]))
    return res
