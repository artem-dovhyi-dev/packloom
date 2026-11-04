"""Loader version lookup and server installer URLs for Forge, NeoForge and Fabric."""
from __future__ import annotations

import re

from .http import get_json, get_text

FORGE_PROMOS = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
FORGE_MAVEN = "https://maven.minecraftforge.net/net/minecraftforge/forge"
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
FABRIC_META = "https://meta.fabricmc.net/v2"


def resolve_loader_version(loader: str, game: str, wanted: str) -> str:
    """`recommended`, `latest` or an explicit version. Returns the explicit version string."""
    if wanted not in ("recommended", "latest"):
        return wanted
    if loader == "forge":
        promos = get_json(FORGE_PROMOS)["promos"]
        return promos.get(f"{game}-{wanted}") or promos.get(f"{game}-latest") or promos[f"{game}-recommended"]
    if loader == "neoforge":
        xml = get_text(f"{NEOFORGE_MAVEN}/maven-metadata.xml")
        nums = [int(x) for x in re.findall(r"\d+", game)] + [0]
        prefix = f"{nums[1]}.{nums[2]}."
        good = [v for v in re.findall(r"<version>([^<]+)</version>", xml) if v.startswith(prefix)]
        if wanted == "recommended":
            good = [v for v in good if "beta" not in v] or good
        return max(good, key=lambda v: [int(x) for x in re.findall(r"\d+", v)])
    if loader in ("fabric", "quilt"):
        loaders = get_json(f"{FABRIC_META}/versions/loader/{game}") or []
        stable = [l for l in loaders if l["loader"].get("stable")] or loaders
        return stable[0]["loader"]["version"]
    raise ValueError(f"unknown loader {loader}")


def mrpack_dependency_key(loader: str) -> str:
    return {"forge": "forge", "neoforge": "neoforge", "fabric": "fabric-loader", "quilt": "quilt-loader"}[loader]


def server_installer_url(loader: str, game: str, version: str) -> str:
    if loader == "forge":
        return f"{FORGE_MAVEN}/{game}-{version}/forge-{game}-{version}-installer.jar"
    if loader == "neoforge":
        return f"{NEOFORGE_MAVEN}/{version}/neoforge-{version}-installer.jar"
    if loader == "fabric":
        installer = (get_json(f"{FABRIC_META}/versions/installer") or [{}])[0].get("version", "1.0.1")
        return f"{FABRIC_META}/versions/loader/{game}/{version}/{installer}/server/jar"
    raise ValueError(f"no server installer for {loader}")
