"""Distribution bundles: a client folder for friends (mrpack + install guide + cheat sheet) and a server folder
(mods, configs, start.sh that installs the loader on first run)."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from .manifest import Pack

START_SH = r'''#!/usr/bin/env sh
# {name} {version} dedicated server. First run downloads and installs {loader} {loader_version}; later runs just start.
# Needs Java {java}. By starting this server you accept Minecraft's EULA (https://aka.ms/MinecraftEULA).
set -e
cd "$(dirname "$0")"
JAVA="${{JAVA:-java}}"
MEM="${{MEM:-{mem}G}}"
if ! "$JAVA" -version >/dev/null 2>&1; then
  echo "java not found. Install Temurin {java} (https://adoptium.net) or run: JAVA=/path/to/java ./start.sh"; exit 1
fi
if [ ! -f run.sh ] && [ ! -f libraries/.installed ]; then
  echo "Installing {loader} {loader_version} server (one time)..."
  curl -fsSL -o installer.jar "{installer_url}"
  "$JAVA" -jar installer.jar --installServer >install.log 2>&1
  rm -f installer.jar
fi
grep -q "eula=true" eula.txt 2>/dev/null || {{ echo "eula=true" > eula.txt; }}
printf -- "-Xms1G\n-Xmx%s\n-XX:+UseG1GC\n-XX:MaxGCPauseMillis=200\n" "$MEM" > user_jvm_args.txt
exec "$JAVA" @user_jvm_args.txt @libraries/net/minecraftforge/forge/{minecraft}-{loader_version}/unix_args.txt nogui "$@"
'''

START_FABRIC_SH = r'''#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
JAVA="${{JAVA:-java}}"; MEM="${{MEM:-{mem}G}}"
grep -q "eula=true" eula.txt 2>/dev/null || echo "eula=true" > eula.txt
exec "$JAVA" -Xms1G -Xmx"$MEM" -jar fabric-server.jar nogui "$@"
'''

SERVER_PROPERTIES = """# {name} {version}: defaults for a small group of friends
online-mode=true
motd={name} {version}
max-players=8
difficulty=normal
gamemode=survival
view-distance=10
simulation-distance=8
spawn-protection=0
enable-command-block=true
white-list=false
level-seed=
pvp=false
allow-flight=true
sync-chunk-writes=false
"""


def _copytree(src: Path, dst: Path, ignore=None):
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)


def _zip_dir(folder: Path, out: Path) -> Path:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, f"{folder.name}/{p.relative_to(folder).as_posix()}")
    return out


def client_bundle(pack: Pack, out_dir: Path, extra_files: list[Path], guide_text: str) -> Path:
    folder = out_dir / f"{pack.name}-{pack.version}-client"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    shutil.copy2(pack.mrpack_path, folder / pack.mrpack_path.name)
    for f in extra_files:
        if f.exists():
            shutil.copy2(f, folder / f.name)
    (folder / "INSTALL.md").write_text(guide_text, encoding="utf-8")
    _zip_dir(folder, out_dir / f"{folder.name}.zip")
    return folder


def server_bundle(pack: Pack, out_dir: Path, loader_version: str, installer_url: str, readme_text: str) -> Path:
    """server/mods + overrides configs + start.sh. The loader itself is installed by start.sh on first run,
    so the bundle stays small and the operator sees exactly what runs."""
    folder = out_dir / f"{pack.name}-{pack.version}-server"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    _copytree(pack.server_dir / "mods", folder / "mods")
    _copytree(pack.overrides / "config", folder / "config")
    _copytree(pack.overrides / "defaultconfigs", folder / "defaultconfigs")
    _copytree(pack.overrides / "kubejs", folder / "kubejs")
    (folder / "server.properties").write_text(SERVER_PROPERTIES.format(name=pack.name, version=pack.version))
    (folder / "eula.txt").write_text("# By running start.sh you accept https://aka.ms/MinecraftEULA\neula=false\n")
    mem = max(4, pack.memory_mb // 1024 + 2)
    tpl = START_FABRIC_SH if pack.loader == "fabric" else START_SH
    (folder / "start.sh").write_text(tpl.format(name=pack.name, version=pack.version, loader=pack.loader,
                                                loader_version=loader_version, minecraft=pack.minecraft, java=pack.java_major,
                                                mem=mem, installer_url=installer_url))
    (folder / "start.sh").chmod(0o755)
    (folder / "README.md").write_text(readme_text, encoding="utf-8")
    manifest = {"name": pack.name, "version": pack.version, "minecraft": pack.minecraft, "loader": pack.loader,
                "loader_version": loader_version, "mods": sorted(p.name for p in (folder / "mods").glob("*.jar"))}
    (folder / "bundle.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _zip_dir(folder, out_dir / f"{folder.name}.zip")
    return folder
