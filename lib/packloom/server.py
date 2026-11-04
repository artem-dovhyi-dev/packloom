"""Install a loader server into <pack>/server and run the smoke test: start, wait for Done or a crash, stop."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Optional

from . import loaders, triage
from .http import download
from .manifest import Pack

RUN_SCRIPT = {"forge": "run.sh", "neoforge": "run.sh"}


def ensure_server(pack: Pack, java: Path, loader_version: str, log=print) -> Path:
    sdir = pack.server_dir
    sdir.mkdir(parents=True, exist_ok=True)
    if pack.loader in ("forge", "neoforge"):
        if not (sdir / "run.sh").exists():
            url = loaders.server_installer_url(pack.loader, pack.minecraft, loader_version)
            installer = sdir / "installer.jar"
            log(f"installing {pack.loader} {loader_version} server from {url}")
            download(url, installer)
            subprocess.run([str(java), "-jar", str(installer), "--installServer"], cwd=sdir, check=True,
                           stdout=open(sdir / "install.log", "w"), stderr=subprocess.STDOUT)
        args = sdir / "user_jvm_args.txt"
        wanted = f"-Xms1G\n-Xmx{max(2048, pack.memory_mb) // 1024}G\n-XX:+UseG1GC\n-XX:MaxGCPauseMillis=200\n"
        if not args.exists() or "-Xmx" not in args.read_text():
            args.write_text(wanted)
    elif pack.loader == "fabric":
        jar = sdir / "fabric-server.jar"
        if not jar.exists():
            url = loaders.server_installer_url("fabric", pack.minecraft, loader_version)
            log(f"downloading fabric server launcher from {url}")
            download(url, jar)
    else:
        raise ValueError(f"server install not supported for {pack.loader}")
    props = sdir / "server.properties"
    if not props.exists():
        props.write_text("online-mode=true\nmax-players=8\nview-distance=8\nlevel-seed=packloom\n")
    return sdir


def accept_eula(pack: Pack) -> None:
    (pack.server_dir / "eula.txt").write_text("# accepted via packloom --accept-eula\neula=true\n")


def eula_accepted(pack: Pack) -> bool:
    p = pack.server_dir / "eula.txt"
    return p.exists() and "eula=true" in p.read_text()


def server_command(pack: Pack) -> list[str]:
    if pack.loader in ("forge", "neoforge"):
        return ["sh", "run.sh", "nogui"]
    return ["java", f"-Xmx{max(2048, pack.memory_mb) // 1024}G", "-jar", "fabric-server.jar", "nogui"]


def mod_ids_from_jars(mods_dir: Path) -> set:
    ids = set()
    for jar in mods_dir.glob("*.jar"):
        try:
            with zipfile.ZipFile(jar) as z:
                for name in ("META-INF/mods.toml", "META-INF/neoforge.mods.toml", "fabric.mod.json"):
                    if name in z.namelist():
                        text = z.read(name).decode("utf-8", "replace")
                        ids |= set(re.findall(r'modId\s*=\s*"([a-z0-9_]+)"', text))
                        m = re.search(r'"id"\s*:\s*"([a-z0-9_-]+)"', text)
                        if m:
                            ids.add(m.group(1))
        except zipfile.BadZipFile:
            continue
    return ids


def smoke_test(pack: Pack, java: Path, timeout: int = 900, log=print) -> dict:
    sdir = pack.server_dir
    if not eula_accepted(pack):
        raise RuntimeError("server/eula.txt lacks eula=true; accept Minecraft's EULA with --accept-eula")
    env = dict(os.environ, PATH=f"{java.parent}:{os.environ['PATH']}", JAVA_HOME=str(java.parent.parent))
    start = time.time()
    proc = subprocess.Popen(server_command(pack), cwd=sdir, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines, ok = [], False
    try:
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            if "Done (" in line and "For help" in line:
                ok = True
                proc.stdin.write("stop\n")
                proc.stdin.flush()
            if time.time() - start > timeout:
                log("timeout, killing server")
                proc.kill()
                break
    finally:
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
    seconds = round(time.time() - start)
    (pack.dir / "smoke-test.log").write_text("\n".join(lines) + "\n", encoding="utf-8")

    crashes = sorted((sdir / "crash-reports").glob("*.txt"), key=os.path.getmtime) if (sdir / "crash-reports").exists() else []
    crash = crashes[-1] if crashes and os.path.getmtime(crashes[-1]) >= start - 5 else None
    crash_text = crash.read_text(errors="replace") if crash else None
    result = triage.analyze(lines, crash_text, mod_ids_from_jars(sdir / "mods"))
    result.ok = ok
    report = {"ok": ok, "seconds": seconds, "java": str(java), "mods_loaded": result.mods_loaded,
              "errors": result.errors[:50], "warnings": result.warnings, "missing_deps": result.missing_deps,
              "crash_report": str(crash) if crash else None,
              "suspects": [s.__dict__ for s in result.suspects], "log": str(pack.dir / "smoke-test.log")}
    (pack.dir / "smoke-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
    log(f"{'OK' if ok else 'FAIL'}: server {'came up' if ok else 'did not come up'} in {seconds}s; "
        f"errors {len(result.errors)}, warnings {result.warnings}")
    if result.mods_loaded:
        log(result.mods_loaded)
    for s in result.suspects:
        log(f"  suspect {s.mod} [{s.kind}] -> {s.action}: {s.evidence[:140]}")
    return report
