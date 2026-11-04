"""Locate a Prism Launcher instance for a pack and read its client logs."""
from __future__ import annotations

import configparser
import os
import platform
from pathlib import Path
from typing import Optional


def data_dir() -> Path:
    env = os.environ.get("PRISM_DATA_DIR")
    if env:
        return Path(env)
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "PrismLauncher"
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", Path.home())) / "PrismLauncher"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "PrismLauncher"


def read_cfg(path: Path) -> dict:
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read(path, encoding="utf-8")
    return dict(cp["General"]) if "General" in cp else {}


def find_instance(pack_name: str, pack_version: Optional[str] = None) -> Optional[Path]:
    """Match ManagedPackName or the instance name; prefer the exact `<name>-<version>` match."""
    root = data_dir() / "instances"
    if not root.exists():
        return None
    wanted = {pack_name.lower()}
    if pack_version:
        wanted.add(f"{pack_name}-{pack_version}".lower())
    best = None
    for cfg in root.glob("*/instance.cfg"):
        g = read_cfg(cfg)
        names = {g.get("ManagedPackName", "").lower(), g.get("name", "").lower(), cfg.parent.name.lower()}
        if names & wanted:
            if pack_version and f"{pack_name}-{pack_version}".lower() in names:
                return cfg.parent
            best = best or cfg.parent
    return best


def game_dir(instance: Path) -> Path:
    for name in ("minecraft", ".minecraft"):
        if (instance / name).is_dir():
            return instance / name
    return instance / "minecraft"


def latest_crash(instance: Path) -> Optional[Path]:
    reports = sorted(game_dir(instance).glob("crash-reports/*.txt"), key=os.path.getmtime)
    return reports[-1] if reports else None


def latest_log(instance: Path) -> Optional[Path]:
    p = game_dir(instance) / "logs" / "latest.log"
    return p if p.exists() else None
