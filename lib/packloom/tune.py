"""tune.json -> KubeJS scripts. The pack author (or the agent) says what should change in plain data:
new items, new recipes, removed recipes, swapped inputs, per-difficulty presets. packloom checks every id
against the registry index, then writes the scripts into overrides/kubejs. Nobody edits the .js by hand."""
from __future__ import annotations

import difflib
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import registry
from .manifest import Pack

ITEM_TYPES = ("basic", "sword", "pickaxe", "axe", "shovel", "hoe", "helmet", "chestplate", "leggings", "boots")
TOOL_TYPES = ("sword", "pickaxe", "axe", "shovel", "hoe")
ARMOR_TYPES = ("helmet", "chestplate", "leggings", "boots")
TIERS = ("wood", "stone", "iron", "gold", "diamond", "netherite")
RARITIES = ("common", "uncommon", "rare", "epic")
DIFFICULTIES = ("easy", "normal", "hard")
RULE_KEYS = ("recipes", "remove", "replace_inputs")
HEADER = "// written by `packloom tune build` from tune.json; edit tune.json, not this file\n"
# recipe types KubeJS edits reliably with replaceInput/remove; a mod's own type (quarryplus:workbench_recipe)
# may not be parsed, and the rule silently does nothing. `tune verify` compares the counts afterwards.
EDITABLE_TYPES = ("minecraft:crafting_shaped", "minecraft:crafting_shapeless", "minecraft:smelting", "minecraft:blasting",
                  "minecraft:smoking", "minecraft:campfire_cooking", "minecraft:stonecutting", "minecraft:smithing_transform")

TEMPLATE = {
    "namespace": "mypack",
    "difficulty": "normal",
    "items": [],
    "recipes": [],
    "remove": [],
    "replace_inputs": [],
    "presets": {"easy": {"recipes": [], "remove": [], "replace_inputs": []},
                "hard": {"recipes": [], "remove": [], "replace_inputs": []}},
}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    items: int = 0
    recipes: int = 0
    removed: int = 0
    replaced: int = 0
    written: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return self.__dict__ | {"ok": self.ok}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("difficulty", "normal") not in DIFFICULTIES:
        raise ValueError(f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    return data


def effective(data: dict) -> dict:
    """Base rules plus the preset of the chosen difficulty. Items are never per preset: an item that exists
    on easy must exist on hard, or worlds break when the preset changes."""
    out = {k: list(data.get(k, [])) for k in RULE_KEYS}
    preset = data.get("presets", {}).get(data.get("difficulty", "normal"), {})
    for k in RULE_KEYS:
        out[k] += list(preset.get(k, []))
    out["items"] = list(data.get("items", []))
    return out


# ---------- validation ----------

class Checker:
    def __init__(self, idx: dict, declared: set[str], report: Report):
        self.idx, self.declared, self.report = idx, declared, report
        self.known_items = set(idx["item"]) | declared
        self.known_tags = set(idx["tag"])

    def item(self, ref: str, where: str) -> None:
        if ref.startswith("#"):
            if ref not in self.known_tags:
                self.report.errors.append(f"{where}: unknown item tag {ref}" + self._hint(ref, self.known_tags))
        elif ref not in self.known_items:
            self.report.errors.append(f"{where}: unknown item {ref}" + self._hint(ref, self.known_items))

    def _hint(self, ref: str, pool: set[str]) -> str:
        close = difflib.get_close_matches(ref, pool, n=3, cutoff=0.75)
        return f" (did you mean {', '.join(close)}?)" if close else ""


def check(data: dict, idx: dict) -> Report:
    rep = Report()
    ns = data.get("namespace", "")
    declared = set()
    for it in data.get("items", []):
        iid = it.get("id", "")
        if ":" not in iid:
            rep.errors.append(f"item {iid!r}: id must be namespace:path"); continue
        if ns and not iid.startswith(ns + ":"):
            rep.errors.append(f"item {iid}: namespace should be {ns!r}")
        if it.get("type", "basic") not in ITEM_TYPES:
            rep.errors.append(f"item {iid}: type must be one of {', '.join(ITEM_TYPES)}")
        if it.get("type") in TOOL_TYPES + ARMOR_TYPES and it.get("tier", "iron") not in TIERS:
            rep.errors.append(f"item {iid}: tier must be one of {', '.join(TIERS)}")
        if it.get("rarity", "common") not in RARITIES:
            rep.errors.append(f"item {iid}: rarity must be one of {', '.join(RARITIES)}")
        if iid in idx["item"]:
            rep.errors.append(f"item {iid}: already exists in a mod; pick another id")
        declared.add(iid)
    rep.items = len(declared)
    ck = Checker(idx, declared, rep)
    eff = effective(data)

    for n, r in enumerate(eff["recipes"], 1):
        where = f"recipe #{n}" + (f" ({r['id']})" if r.get("id") else "")
        t = r.get("type", "shaped")
        if t == "shaped":
            for row in r.get("pattern", []):
                for ch in row:
                    if ch != " " and ch not in r.get("key", {}):
                        rep.errors.append(f"{where}: pattern uses {ch!r} but key has no entry for it")
            for ch, ref in r.get("key", {}).items():
                ck.item(ref, f"{where} key {ch}")
            ck.item(r.get("result", ""), f"{where} result")
        elif t == "shapeless":
            for ref in r.get("inputs", []):
                ck.item(ref, f"{where} input")
            ck.item(r.get("result", ""), f"{where} result")
        elif t == "custom":
            if not isinstance(r.get("json"), dict) or "type" not in r["json"]:
                rep.errors.append(f"{where}: custom recipe needs a `json` object with a `type`")
            else:
                for ref in registry._ids_in(r["json"]):
                    if ref != r["json"]["type"] and not ref.startswith("#forge:") and ":" in ref:
                        ck.item(ref, f"{where} json")
        else:
            rep.errors.append(f"{where}: type must be shaped, shapeless or custom")
    rep.recipes = len(eff["recipes"])

    for n, rm in enumerate(eff["remove"], 1):
        where = f"remove #{n}"
        if not isinstance(rm, dict) or not rm:
            rep.errors.append(f"{where}: must be an object like {{\"id\": \"ns:path\"}} or {{\"output\": \"ns:item\"}}"); continue
        try:
            hits = registry.recipes_matching(idx, rm)
        except ValueError as e:
            rep.errors.append(f"{where}: {e}"); continue
        if not hits:
            rep.errors.append(f"{where}: no recipe matches {json.dumps(rm)}")
        else:
            rep.notes.append(f"{where}: removes {len(hits)} recipe(s): {', '.join(hits[:5])}{'…' if len(hits) > 5 else ''}")
            rep.removed += len(hits)

    for n, rp in enumerate(eff["replace_inputs"], 1):
        where = f"replace_inputs #{n}"
        src, dst, where_filter = rp.get("from", ""), rp.get("to", ""), rp.get("in", {})
        ck.item(src, f"{where} from"); ck.item(dst, f"{where} to")
        try:
            hits = [h for h in registry.recipes_matching(idx, where_filter) if src in idx["recipe"][h]["inputs"]]
        except ValueError as e:
            rep.errors.append(f"{where}: {e}"); continue
        if not hits:
            rep.errors.append(f"{where}: no recipe matching {json.dumps(where_filter)} uses {src}")
        else:
            rep.notes.append(f"{where}: {src} -> {dst} in {len(hits)} recipe(s): {', '.join(hits[:5])}{'…' if len(hits) > 5 else ''}")
            rep.replaced += len(hits)
            odd = [h for h in hits if idx["recipe"][h].get("type") not in EDITABLE_TYPES]
            for h in odd:
                rep.warnings.append(f"{where}: {h} has type {idx['recipe'][h].get('type')}, which KubeJS may not be able to edit; "
                                    f"`tune verify` after the server run tells")
    return rep


# ---------- script generation ----------

def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def startup_script(items: list[dict]) -> str:
    lines = [HEADER, "StartupEvents.registry('item', event => {"]
    for it in items:
        t = it.get("type", "basic")
        call = f"  event.create({js_str(it['id'])}" + (f", {js_str(t)})" if t != "basic" else ")")
        if t in TOOL_TYPES + ARMOR_TYPES:
            call += f".tier({js_str(it.get('tier', 'iron'))})"
        if t in TOOL_TYPES and "attack_damage_bonus" in it:
            call += f".attackDamageBonus({float(it['attack_damage_bonus'])})"
        if t in TOOL_TYPES and "attack_speed" in it:
            call += f".speedBaseline({float(it['attack_speed'])})"
        call += f".displayName({js_str(it.get('name', it['id'].split(':')[1]))})"
        if it.get("rarity", "common") != "common":
            call += f".rarity({js_str(it['rarity'])})"
        if it.get("glow"):
            call += ".glow(true)"
        if t == "basic" and it.get("max_stack"):
            call += f".maxStackSize({int(it['max_stack'])})"
        for tip in it.get("tooltip", []):
            call += f".tooltip({js_str(tip)})"
        lines.append(call)
    lines.append("})")
    return "\n".join(lines) + "\n"


def _filter_js(f: dict) -> str:
    return "{" + ", ".join(f"{k}: {js_str(v)}" for k, v in f.items()) + "}"


def server_script(eff: dict) -> str:
    lines = [HEADER, "ServerEvents.recipes(event => {"]
    for r in eff["recipes"]:
        t = r.get("type", "shaped")
        count = int(r.get("count", 1))
        result = f"Item.of({js_str(r.get('result', ''))}, {count})"
        rid = f".id({js_str(r['id'])})" if r.get("id") else ""
        if t == "shaped":
            pattern = "[" + ", ".join(js_str(row) for row in r["pattern"]) + "]"
            keys = "{" + ", ".join(f"{js_str(k)}: {js_str(v)}" for k, v in r["key"].items()) + "}"
            lines.append(f"  event.shaped({result}, {pattern}, {keys}){rid}")
        elif t == "shapeless":
            inputs = "[" + ", ".join(js_str(i) for i in r["inputs"]) + "]"
            lines.append(f"  event.shapeless({result}, {inputs}){rid}")
        elif t == "custom":
            lines.append(f"  event.custom({json.dumps(r['json'], ensure_ascii=False)}){rid}")
    for rm in eff["remove"]:
        lines.append(f"  event.remove({_filter_js(rm)})")
    for rp in eff["replace_inputs"]:
        lines.append(f"  event.replaceInput({_filter_js(rp.get('in', {}))}, {js_str(rp['from'])}, {js_str(rp['to'])})")
    lines.append("})")
    return "\n".join(lines) + "\n"


# ---------- placeholder icons (16x16 PNG, stdlib only) ----------

def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _shade(rgb, f: float):
    return tuple(max(0, min(255, int(v * f))) for v in rgb)


def icon_pixels(shape: str, color: str) -> list[list[tuple]]:
    base = _hex(color)
    light, dark, handle = _shade(base, 1.35), _shade(base, 0.6), (70, 48, 30)
    px = [[(0, 0, 0, 0)] * 16 for _ in range(16)]

    def put(x, y, c):
        if 0 <= x < 16 and 0 <= y < 16:
            px[y][x] = (*c, 255)

    if shape == "blade":
        for i in range(11):                      # diagonal blade from bottom-left to top-right
            x, y = 4 + i, 11 - i
            put(x, y, light); put(x + 1, y, base); put(x, y + 1, dark)
        for i in range(3):                       # guard
            put(3 + i, 11 + i, (190, 190, 200)); put(5 - i, 9 + i, (190, 190, 200))
        for i in range(3):                       # handle
            put(2 + i, 13 - i, handle); put(1 + i, 13 - i, handle)
        put(1, 14, (240, 200, 60))               # pommel
    elif shape == "ingot":
        for y in range(6, 11):
            off = 10 - y
            for x in range(3 + off, 12 + off):
                put(x, y, light if y == 6 else dark if y == 10 else base)
    elif shape == "gem":
        for y in range(3, 13):
            w = y - 3 if y < 8 else 12 - y
            for x in range(8 - w, 8 + w + 1):
                put(x, y, light if (x + y) % 3 == 0 else base if y < 8 else dark)
    elif shape == "orb":
        for y in range(16):
            for x in range(16):
                d = (x - 7.5) ** 2 + (y - 7.5) ** 2
                if d <= 30:
                    put(x, y, light if d <= 8 and x < 8 and y < 8 else base if d <= 22 else dark)
    else:  # tool: stick with a head
        for i in range(9):
            put(3 + i, 12 - i, handle); put(4 + i, 12 - i, (110, 78, 48))
        for y in range(2, 7):
            for x in range(9, 15):
                put(x, y, light if y == 2 else dark if y == 6 else base)
    return px


def write_png(path: Path, px: list[list[tuple]]) -> None:
    h, w = len(px), len(px[0])
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ---------- entry points ----------

def init(pack: Pack, namespace: str) -> Path:
    path = pack.dir / "tune.json"
    if not path.exists():
        data = dict(TEMPLATE, namespace=namespace)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build(pack: Pack, idx: dict, data: Optional[dict] = None, write: bool = True) -> Report:
    data = data or load(pack.dir / "tune.json")
    rep = check(data, idx)
    if not rep.ok or not write:
        return rep
    eff = effective(data)
    kube = pack.overrides / "kubejs"
    ns = data.get("namespace", "mypack")
    targets = {kube / "startup_scripts" / "packloom.items.js": startup_script(eff["items"]),
               kube / "server_scripts" / "packloom.tune.js": server_script(eff)}
    for path, text in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        rep.written.append(str(path.relative_to(pack.dir)))
    for it in eff["items"]:
        name = it["id"].split(":", 1)[1]
        png = kube / "assets" / ns / "textures" / "item" / f"{name}.png"
        if not png.exists():                     # a real texture dropped here is never overwritten
            icon = it.get("icon", {})
            write_png(png, icon_pixels(icon.get("shape", "tool" if it.get("type") in TOOL_TYPES else "gem"),
                                       icon.get("color", "#8a8aff")))
            rep.written.append(str(png.relative_to(pack.dir)))
    return rep


def verify_logs(pack: Pack, expected: Optional[Report] = None) -> dict:
    """After a server run: did KubeJS load the scripts, how many recipes changed, any script errors? With
    `expected` (a check() report), the server's added/removed/modified counts are compared to tune.json's."""
    out = {"kubejs_seen": False, "summary": "", "errors": [], "mismatch": []}
    candidates = [pack.dir / "smoke-test.log", pack.server_dir / "logs" / "kubejs" / "server.log",
                  pack.server_dir / "kubejs" / "server.log", pack.server_dir / "logs" / "kubejs" / "startup.log"]
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text(errors="replace").splitlines():
            low = line.lower()
            if "kubejs" in low:
                out["kubejs_seen"] = True
            if "recipes" in low and ("added" in low or "removed" in low or "modified" in low) and "kubejs" in low:
                out["summary"] = line.strip()[-200:]
            if "kubejs" in low and ("error" in low or "exception" in low) and "packloom" in low:
                out["errors"].append(line.strip()[:300])
            if "packloom.tune.js" in low and ("error" in low or "exception" in low):
                out["errors"].append(line.strip()[:300])
    m = re.search(r"Added (\d+) recipes, removed (\d+) recipes, modified (\d+) recipes, with (\d+) failed", out["summary"])
    if m:
        added, removed, modified, failed = map(int, m.groups())
        out["counts"] = {"added": added, "removed": removed, "modified": modified, "failed": failed}
        if failed:
            out["errors"].append(f"{failed} recipe(s) failed to register; look for them in server/logs/kubejs/server.log")
        if expected is not None:
            for name, want, got in (("added", expected.recipes, added), ("removed", expected.removed, removed), ("modified", expected.replaced, modified)):
                if want != got:
                    out["mismatch"].append(f"{name}: tune.json expects {want}, the server {name} {got}"
                                           + (" (a rule on a recipe type KubeJS cannot edit?)" if got < want else ""))
    return out
