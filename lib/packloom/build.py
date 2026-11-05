"""Resolve mods.txt against Modrinth, fetch non-Modrinth jars, write the .mrpack and a build report."""
from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import loaders, modrinth, sources
from .http import download
from .manifest import ModEntry, Pack


@dataclass
class BuildResult:
    mrpack: Path
    loader_version: str
    files: list[dict]
    missing: list[tuple[str, str]]
    manual: list[ModEntry]
    overrides_jars: list[str] = field(default_factory=list)

    @property
    def report_json(self) -> dict:
        return {"mrpack": str(self.mrpack), "loader_version": self.loader_version, "files": len(self.files),
                "missing": [{"ref": r, "why": w} for r, w in self.missing],
                "manual": [{"name": m.ref, "note": m.comment} for m in self.manual],
                "overrides_jars": self.overrides_jars}


def env_of(project: dict, entry: Optional[ModEntry]) -> dict:
    """Client is always required: singleplayer runs an integrated server, so worldgen and logic are needed
    there too. Server is unsupported only when Modrinth says so, or the entry says `client`."""
    side = entry.side if entry else None
    if side == "client":
        return {"client": "required", "server": "unsupported"}
    if side == "server":
        return {"client": "unsupported", "server": "required"}
    server = "unsupported" if project.get("server_side") == "unsupported" else "required"
    return {"client": "required", "server": server}


def build(pack: Pack, out: Optional[Path] = None, want_server: bool = False, log=print) -> BuildResult:
    entries = pack.entries()
    log(f"Building {pack.name} {pack.version} for Minecraft {pack.minecraft} {pack.loader}\n")
    res = modrinth.resolve(entries, pack.minecraft, pack.loader, log)
    fetched = sources.fetch_overrides(pack, entries, log)
    loader_version = loaders.resolve_loader_version(pack.loader, pack.minecraft, pack.loader_version)

    files = []
    for r in res.resolved.values():
        f = modrinth.primary_file(r.version)
        env = env_of(r.project, r.entry) if r.folder == "mods" else {"client": "required", "server": "unsupported"}
        files.append({"path": f"{r.folder}/{f['filename']}", "hashes": f["hashes"], "env": env,
                      "downloads": [f["url"]], "fileSize": f["size"]})
    files.sort(key=lambda e: e["path"])

    index = {"formatVersion": 1, "game": "minecraft", "versionId": pack.version, "name": pack.name,
             "dependencies": {"minecraft": pack.minecraft,
                              loaders.mrpack_dependency_key(pack.loader): loader_version},
             "files": files}
    apply_visual_defaults(pack, files, log)
    out = out or pack.mrpack_path
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("modrinth.index.json", json.dumps(index, indent=2, ensure_ascii=False))
        if pack.overrides.exists():
            for p in sorted(pack.overrides.rglob("*")):
                if p.is_file() and not p.name.startswith("."):
                    z.write(p, "overrides/" + p.relative_to(pack.overrides).as_posix())

    manual = [e for e in entries if e.source == "manual"]
    result = BuildResult(mrpack=out, loader_version=loader_version, files=files, missing=res.missing,
                         manual=manual, overrides_jars=[p.name for _, p in fetched])
    write_report(pack, result, res)
    log(f"\n{out.name}: {len(files)} files, {pack.loader} {loader_version}")
    for ref, why in res.missing:
        log(f"  MISSING {ref}: {why}")
    for m in manual:
        log(f"  MANUAL  {m.ref}: {m.comment}")
    if want_server:
        sync_server_mods(pack, files, log)
        sync_server_overrides(pack, log)
    return result


SHADER_CONFIG = {"forge": "oculus.properties", "neoforge": "oculus.properties", "fabric": "iris.properties", "quilt": "iris.properties"}


def apply_visual_defaults(pack: Pack, files: list[dict], log=print) -> dict:
    """Resource packs and shader packs in the index are enabled by default: `resourcePacks:` in
    overrides/options.txt lists every resourcepacks/ file (other lines are kept), and the shader loader's
    config names the first shaderpacks/ file. Prism and the Modrinth app apply overrides on import, so a
    friend who installs the mrpack sees the textures and shaders without touching a menu."""
    packs = [Path(e["path"]).name for e in files if e["path"].startswith("resourcepacks/")]
    shaders = [Path(e["path"]).name for e in files if e["path"].startswith("shaderpacks/")]
    done = {}
    if packs:
        opts = pack.overrides / "options.txt"
        lines = opts.read_text(encoding="utf-8").splitlines() if opts.exists() else []
        value = "resourcePacks:" + json.dumps(["vanilla", "mod_resources"] + [f"file/{n}" for n in packs])
        lines = [l for l in lines if not l.startswith("resourcePacks:")]
        lines.insert(0, value)
        opts.parent.mkdir(parents=True, exist_ok=True)
        opts.write_text("\n".join(lines) + "\n", encoding="utf-8")
        done["resourcepacks"] = packs
        log(f"  options.txt: resource packs on by default: {', '.join(packs)}")
    if shaders:
        cfg = pack.overrides / "config" / SHADER_CONFIG.get(pack.loader, "oculus.properties")
        lines = cfg.read_text(encoding="utf-8").splitlines() if cfg.exists() else []
        lines = [l for l in lines if not l.startswith(("shaderPack=", "enableShaders="))]
        lines = [f"shaderPack={shaders[0]}", "enableShaders=true"] + lines
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
        done["shaderpack"] = shaders[0]
        log(f"  {cfg.name}: shader pack on by default: {shaders[0]}")
    return done


def write_report(pack: Pack, result: BuildResult, res: modrinth.Resolution) -> None:
    lines = [f"# Build report: {pack.name} {pack.version}", "",
             f"Minecraft {pack.minecraft}, {pack.loader} {result.loader_version}, files: {len(result.files)}", "",
             "| File | Client | Server | Required by |", "|---|---|---|---|"]
    by_path = {}
    for r in res.resolved.values():
        by_path[f"{r.folder}/{modrinth.primary_file(r.version)['filename']}"] = r
    for e in result.files:
        r = by_path.get(e["path"])
        req = ", ".join(r.required_by) if r and r.required_by else ""
        lines.append(f"| {e['path']} | {e['env']['client']} | {e['env']['server']} | {req} |")
    if result.overrides_jars:
        lines += ["", "## Shipped in overrides/mods", ""] + [f"- {n}" for n in result.overrides_jars]
    if result.manual:
        lines += ["", "## Manual install", ""] + [f"- {m.ref}: {m.comment}" for m in result.manual]
    if result.missing:
        lines += ["", "## Not found", ""] + [f"- {r}: {w}" for r, w in result.missing]
    (pack.dir / "build-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (pack.dir / "build-report.json").write_text(json.dumps(result.report_json, indent=2, ensure_ascii=False) + "\n",
                                                encoding="utf-8")


def sync_server_mods(pack: Pack, files: list[dict], log=print) -> Path:
    """server/mods = every server-side jar from the index plus overrides/mods; stale jars are removed."""
    sdir = pack.server_dir / "mods"
    sdir.mkdir(parents=True, exist_ok=True)
    keep = {Path(e["path"]).name for e in files if e["path"].startswith("mods/") and e["env"]["server"] != "unsupported"}
    overrides = list((pack.overrides / "mods").glob("*.jar")) if (pack.overrides / "mods").exists() else []
    keep |= {p.name for p in overrides}
    for old in sdir.glob("*.jar"):
        if old.name not in keep:
            old.unlink()
            log(f"  removed stale {old.name}")
    for src in overrides:
        dest = sdir / src.name
        if not dest.exists():
            dest.write_bytes(src.read_bytes())
    for e in files:
        name = Path(e["path"]).name
        if name in keep and e["path"].startswith("mods/") and not (sdir / name).exists():
            download(e["downloads"][0], sdir / name, sha1=e["hashes"].get("sha1"))
    log(f"server mods: {sdir} ({len(list(sdir.glob('*.jar')))} jars)")
    return sdir


SERVER_OVERRIDE_DIRS = ("config", "defaultconfigs", "kubejs")


def sync_server_overrides(pack: Pack, log=print) -> list[Path]:
    """server/config and server/defaultconfigs follow overrides/: a file is copied over, a directory is replaced
    whole (the pack owns it: quests, datapacks), everything else the server generated is left alone."""
    touched = []
    for sub in SERVER_OVERRIDE_DIRS:
        src = pack.overrides / sub
        if not src.is_dir():
            continue
        dest = pack.server_dir / sub
        dest.mkdir(parents=True, exist_ok=True)
        for child in sorted(src.iterdir()):
            target = dest / child.name
            if child.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
            touched.append(target)
    if touched:
        log(f"server overrides: {len(touched)} entries synced into {pack.server_dir}")
    return touched
