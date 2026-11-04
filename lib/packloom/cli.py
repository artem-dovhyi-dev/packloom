"""packloom command line. Every skill script calls main() with a subcommand."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import build as build_mod, keybinds, loaders, modrinth, prism, server, triage
from .java import find_java
from .manifest import Pack, find_pack_dir, load_pack, write_pack


def _pack(args) -> Pack:
    d = Path(args.pack) if args.pack else find_pack_dir(Path.cwd())
    if d is None:
        sys.exit("no pack.json found here; pass --pack <dir> or run `packloom init`")
    return load_pack(d)


def cmd_init(args):
    d = Path(args.dir).resolve()
    d.mkdir(parents=True, exist_ok=True)
    if (d / "pack.json").exists() and not args.force:
        sys.exit(f"{d / 'pack.json'} exists; use --force to overwrite")
    pack = Pack(dir=d, name=args.name, version=args.version, minecraft=args.minecraft, loader=args.loader,
                loader_version=args.loader_version, memory_mb=args.memory)
    write_pack(pack)
    mods = d / "mods.txt"
    if not mods.exists():
        mods.write_text("# One entry per line. See `packloom help-syntax`.\n# slug | slug@1.2.3 | slug client | ftb:artifact | url:https://... | manual:name\n\n")
    (d / "overrides").mkdir(exist_ok=True)
    print(f"initialised {pack.name} {pack.version} ({pack.minecraft} {pack.loader}) in {d}")


def cmd_search(args):
    pack = _pack(args)
    hits = modrinth.search(args.query, pack.minecraft, pack.loader, args.limit, args.type)
    if args.json:
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return
    for h in hits:
        print(f"{h['slug']:36} {h['downloads']:>10}  {h.get('server_side','?'):11} {h['title']} — {h['description'][:90]}")


def cmd_info(args):
    pack = _pack(args)
    proj = modrinth.project(args.slug)
    if not proj:
        sys.exit(f"{args.slug}: not found on Modrinth")
    found = modrinth.versions(proj["id"], pack.minecraft, pack.loader, proj["project_type"])
    out = {"slug": proj["slug"], "title": proj["title"], "type": proj["project_type"], "client": proj.get("client_side"),
           "server": proj.get("server_side"), "description": proj["description"],
           "versions": [{"number": v["version_number"], "type": v["version_type"], "date": v["date_published"][:10],
                         "deps": [d.get("project_id") for d in v.get("dependencies", []) if d.get("dependency_type") == "required"]}
                        for v in found[:8]]}
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_build(args):
    pack = _pack(args)
    result = build_mod.build(pack, out=Path(args.out) if args.out else None, want_server=args.server)
    if args.json:
        print(json.dumps(result.report_json, indent=2, ensure_ascii=False))
    sys.exit(1 if result.missing and args.strict else 0)


def _java(pack: Pack, args) -> Path:
    if args.java:
        return Path(args.java)
    return find_java(pack.java_major, allow_download=not args.no_download_java)


def cmd_test(args):
    pack = _pack(args)
    report_json = pack.dir / "build-report.json"
    if not args.skip_build or not report_json.exists():
        result = build_mod.build(pack, want_server=True)
        loader_version = result.loader_version
    else:
        data = json.loads(report_json.read_text())
        loader_version = data["loader_version"]
        build_mod.sync_server_mods(pack, _files_from_mrpack(pack))
    java = _java(pack, args)
    server.ensure_server(pack, java, loader_version)
    if args.accept_eula:
        server.accept_eula(pack)
    report = server.smoke_test(pack, java, timeout=args.timeout)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["ok"] else 1)


def _files_from_mrpack(pack: Pack) -> list:
    import zipfile
    with zipfile.ZipFile(pack.mrpack_path) as z:
        return json.loads(z.read("modrinth.index.json"))["files"]


def cmd_triage(args):
    pack = _pack(args)
    lines, crash_text, source = [], None, ""
    if args.client:
        inst = prism.find_instance(pack.name, pack.version)
        if not inst:
            sys.exit(f"no Prism instance found for {pack.name}")
        log, crash = prism.latest_log(inst), prism.latest_crash(inst)
        lines = log.read_text(errors="replace").splitlines() if log else []
        crash_text = crash.read_text(errors="replace") if crash else None
        source = f"prism instance {inst}"
        mods_dir = prism.game_dir(inst) / "mods"
    else:
        log = Path(args.log) if args.log else pack.dir / "smoke-test.log"
        lines = log.read_text(errors="replace").splitlines() if log.exists() else []
        crash = Path(args.crash) if args.crash else None
        crash_text = crash.read_text(errors="replace") if crash and crash.exists() else None
        source = str(log)
        mods_dir = pack.server_dir / "mods"
    t = triage.analyze(lines, crash_text, server.mod_ids_from_jars(mods_dir) if mods_dir.exists() else set())
    out = {"source": source, **t.as_dict()}
    out["errors"] = out["errors"][:30]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_keys(args):
    pack = _pack(args) if (args.pack or not args.options) else None
    if args.options:
        options = Path(args.options)
    else:
        inst = prism.find_instance(pack.name, pack.version)
        if not inst:
            sys.exit(f"no Prism instance found for {pack.name}; pass --options <file>")
        options = prism.game_dir(inst) / "options.txt"
    binds = keybinds.parse_options(options.read_text(errors="replace"))
    if args.json:
        print(json.dumps(keybinds.summary(binds), indent=2, ensure_ascii=False))
    out = Path(args.out) if args.out else (pack.dir if pack else options.parent) / "keybinds.html"
    out.write_text(keybinds.render_html(binds, f"{pack.name if pack else options.parent.name} keybinds"), encoding="utf-8")
    s = keybinds.summary(binds)
    print(f"{out}: {s['bound']} bound, {s['unbound']} unbound, {len(s['conflicts'])} conflicts, {len(s['mods'])} mods")


def cmd_prism(args):
    pack = _pack(args)
    inst = prism.find_instance(pack.name, pack.version)
    if not inst:
        sys.exit(f"no Prism instance found for {pack.name} under {prism.data_dir()}")
    cfg = prism.read_cfg(inst / "instance.cfg")
    print(json.dumps({"instance": str(inst), "game_dir": str(prism.game_dir(inst)),
                      "java": cfg.get("JavaPath"), "max_mem": cfg.get("MaxMemAlloc"), "last_launch": cfg.get("lastLaunchTime"),
                      "latest_log": str(prism.latest_log(inst) or ""), "latest_crash": str(prism.latest_crash(inst) or "")},
                     indent=2))


def cmd_help_syntax(args):
    print(Path(__file__).with_name("SYNTAX.md").read_text())


def main(argv=None):
    p = argparse.ArgumentParser(prog="packloom", description="Minecraft modpack as plain text, built and verified by an agent")
    p.add_argument("--pack", help="pack directory (default: the one holding pack.json near cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create pack.json and mods.txt"); s.set_defaults(fn=cmd_init)
    s.add_argument("--dir", default="."); s.add_argument("--name", required=True); s.add_argument("--version", default="0.1.0")
    s.add_argument("--minecraft", required=True); s.add_argument("--loader", required=True, choices=["forge", "neoforge", "fabric", "quilt"])
    s.add_argument("--loader-version", default="recommended"); s.add_argument("--memory", type=int, default=4096); s.add_argument("--force", action="store_true")

    s = sub.add_parser("search", help="search Modrinth for the pack's game and loader"); s.set_defaults(fn=cmd_search)
    s.add_argument("query"); s.add_argument("--limit", type=int, default=8); s.add_argument("--type", default="mod"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("info", help="project details and compatible versions"); s.set_defaults(fn=cmd_info); s.add_argument("slug")

    s = sub.add_parser("build", help="resolve mods.txt and write the .mrpack"); s.set_defaults(fn=cmd_build)
    s.add_argument("--out"); s.add_argument("--server", action="store_true", help="also sync server/mods"); s.add_argument("--json", action="store_true")
    s.add_argument("--strict", action="store_true", help="exit 1 when any entry is missing")

    s = sub.add_parser("test", help="install the server if needed and run the smoke test"); s.set_defaults(fn=cmd_test)
    s.add_argument("--accept-eula", action="store_true", help="write eula=true (a human decision)"); s.add_argument("--timeout", type=int, default=900)
    s.add_argument("--java"); s.add_argument("--no-download-java", action="store_true"); s.add_argument("--skip-build", action="store_true"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("triage", help="suspect mods from a log or crash report"); s.set_defaults(fn=cmd_triage)
    s.add_argument("--client", action="store_true", help="read the Prism instance's latest.log and crash report"); s.add_argument("--log"); s.add_argument("--crash")

    s = sub.add_parser("keys", help="keyboard map from options.txt"); s.set_defaults(fn=cmd_keys)
    s.add_argument("--options"); s.add_argument("--out"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("prism", help="locate the Prism instance for this pack"); s.set_defaults(fn=cmd_prism)
    s = sub.add_parser("help-syntax", help="print the mods.txt and pack.json syntax"); s.set_defaults(fn=cmd_help_syntax)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
