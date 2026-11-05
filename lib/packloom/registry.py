"""Registry index: every item, block, entity, dimension, item tag and recipe that the pack's jars define.
Read from the jars themselves (models, blockstates, lang, data/), so a script or quest can be checked
against what will really exist in the game, before the server is ever started."""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable, Optional

KEY_RE = re.compile(r"^(item|block|entity)\.([a-z0-9_]+)\.([a-z0-9_./]+)$")
ITEM_MODEL = re.compile(r"^assets/([a-z0-9_]+)/models/item/([a-z0-9_./]+)\.json$")
BLOCKSTATE = re.compile(r"^assets/([a-z0-9_]+)/blockstates/([a-z0-9_./]+)\.json$")
DIMENSION = re.compile(r"^data/([a-z0-9_]+)/dimension/([a-z0-9_./]+)\.json$")
RECIPE = re.compile(r"^data/([a-z0-9_]+)/recipes/([a-z0-9_./-]+)\.json$")
ITEM_TAG = re.compile(r"^data/([a-z0-9_]+)/tags/items/([a-z0-9_./-]+)\.json$")


def empty() -> dict:
    return {"item": {}, "block": {}, "entity": {}, "dimension": [], "tag": [], "recipe": {}, "jars": []}


def _walk(z: zipfile.ZipFile):
    """Yield (zip, name) for every entry, descending into jar-in-jar (META-INF/jarjar/*.jar)."""
    for n in z.namelist():
        if n.startswith("META-INF/jarjar/") and n.endswith(".jar"):
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(n))) as inner:
                    yield from _walk(inner)
            except zipfile.BadZipFile:
                continue
        else:
            yield z, n


def _ids_in(obj) -> set[str]:
    """Every `item`/`tag` reference inside a recipe json, whatever the recipe type's shape."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "item" and isinstance(v, str):
                out.add(v)
            elif k == "tag" and isinstance(v, str):
                out.add("#" + v)
            else:
                out |= _ids_in(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _ids_in(v)
    elif isinstance(obj, str) and re.match(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$", obj):
        out.add(obj)
    return out


def _result_of(rec: dict) -> Optional[str]:
    for k in ("result", "output", "results"):
        v = rec.get(k)
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            for kk in ("item", "id"):
                if isinstance(v.get(kk), str):
                    return v[kk]
        if isinstance(v, list) and v:
            return _result_of({"result": v[0]})
    return None


def index_jar(path: Path, out: dict) -> None:
    with zipfile.ZipFile(path) as zz:
        out["jars"].append(path.name)
        for z, n in _walk(zz):
            if n.startswith("assets/") and n.endswith("/lang/en_us.json"):
                try:
                    lang = json.loads(z.read(n).decode("utf-8-sig"))
                except Exception:
                    continue
                for k, v in lang.items():
                    m = KEY_RE.match(k)
                    if m and "." not in m.group(3) and isinstance(v, str):
                        out[m.group(1)][f"{m.group(2)}:{m.group(3)}"] = v
                continue
            m = ITEM_MODEL.match(n)
            if m:
                out["item"].setdefault(f"{m.group(1)}:{m.group(2)}", ""); continue
            m = BLOCKSTATE.match(n)
            if m:
                out["block"].setdefault(f"{m.group(1)}:{m.group(2)}", ""); continue
            m = DIMENSION.match(n)
            if m:
                out["dimension"].append(f"{m.group(1)}:{m.group(2)}"); continue
            m = ITEM_TAG.match(n)
            if m:
                out["tag"].append(f"#{m.group(1)}:{m.group(2)}"); continue
            m = RECIPE.match(n)
            if m:
                try:
                    rec = json.loads(z.read(n).decode("utf-8-sig"))
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                rid = f"{m.group(1)}:{m.group(2)}"
                result = _result_of(rec)
                inputs = sorted(_ids_in({k: v for k, v in rec.items() if k not in ("result", "output", "results", "type")}))
                out["recipe"][rid] = {"type": rec.get("type", ""), "result": result, "inputs": inputs}


def base_jars(server_dir: Path, prism_libraries: Optional[Path] = None) -> list[Path]:
    """Jars that define ids no mod jar holds: vanilla data/ and assets/ (Forge's `-extra.jar` under
    server/libraries, else the Prism client jar) and the loader's own jar (Forge's `-universal.jar`, which
    defines the forge: item tags). Without them `minecraft:` ids and `#forge:` tags are unknown."""
    out: list[Path] = []
    mc = server_dir / "libraries" / "net" / "minecraft" / "server"
    extra = sorted(mc.rglob("*-extra.jar"))
    if extra:
        out.append(extra[0])
    elif prism_libraries:
        client = sorted(prism_libraries.rglob("minecraft-*-client.jar"))
        if client:
            out.append(client[0])
    for loader_dir in (server_dir / "libraries" / "net" / "minecraftforge" / "forge",
                       server_dir / "libraries" / "net" / "neoforged" / "neoforge"):
        out += sorted(loader_dir.rglob("*-universal.jar"))[:1]
    return out


def vanilla_jar(server_dir: Path, prism_libraries: Optional[Path] = None) -> Optional[Path]:
    jars = base_jars(server_dir, prism_libraries)
    return jars[0] if jars else None


def build_index(jars: Iterable[Path]) -> dict:
    out = empty()
    for jar in jars:
        try:
            index_jar(jar, out)
        except zipfile.BadZipFile:
            continue
    out["dimension"] = sorted(set(out["dimension"]))
    out["tag"] = sorted(set(out["tag"]))
    return out


def counts(idx: dict) -> dict:
    return {k: len(v) for k, v in idx.items() if k != "jars"} | {"jars": len(idx["jars"])}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(idx: dict, path: Path) -> None:
    path.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def recipes_matching(idx: dict, where: dict) -> list[str]:
    """KubeJS-style filter over the registry; see match_recipes."""
    return match_recipes(idx["recipe"], where)


def match_recipes(recipes: dict, where: dict) -> list[str]:
    """KubeJS-style filter: {"id": "ns:path"} | {"mod": "ns"} | {"output": "ns:item"} | {"type": "ns:type"}
    | {"input": "ns:item"}; several keys AND together. `recipes` maps id -> {type, result, inputs}."""
    hits = []
    for rid, rec in recipes.items():
        ok = True
        for k, v in where.items():
            if k == "id":
                ok &= rid == v
            elif k == "mod":
                ok &= rid.split(":", 1)[0] == v
            elif k == "output":
                ok &= rec.get("result") == v
            elif k == "type":
                ok &= rec.get("type") == v
            elif k == "input":
                ok &= v in rec.get("inputs", [])
            else:
                raise ValueError(f"unknown recipe filter key {k!r}")
        if ok:
            hits.append(rid)
    return hits


def namespaces(idx: dict) -> set[str]:
    """Mod ids that define at least one item."""
    return {i.split(":", 1)[0] for i in idx["item"]}
