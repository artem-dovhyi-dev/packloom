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
TIERS_OF_PLAY = ("early", "mid", "late")
# keys whose `tag` is a fluid or chemical tag, not an item tag (Mekanism, Thermal); such tags are not checked
NON_ITEM_KEYS = ("chemicalInput", "gasInput", "fluidInput", "infusionInput", "pigmentInput", "slurryInput", "fluid", "gas",
                 "infuse_type", "pigment", "slurry", "circumstance")
HEADER = "// written by `packloom tune build` from tune.json; edit tune.json, not this file\n"
# recipe types KubeJS edits reliably with replaceInput/remove; a mod's own type (quarryplus:workbench_recipe)
# may not be parsed, and the rule silently does nothing. `tune verify` compares the counts afterwards.
EDITABLE_TYPES = ("minecraft:crafting_shaped", "minecraft:crafting_shapeless", "minecraft:smelting", "minecraft:blasting",
                  "minecraft:smoking", "minecraft:campfire_cooking", "minecraft:stonecutting", "minecraft:smithing_transform")

TEMPLATE = {
    "namespace": "mypack",
    "difficulty": "normal",
    "items": [],
    "integrations": [],
    "recipes": [],
    "remove": [],
    "replace_inputs": [],
    "presets": {"easy": {"recipes": [], "remove": [], "replace_inputs": []},
                "hard": {"recipes": [], "remove": [], "replace_inputs": []}},
}
# one integration = one bridge between two (or more) mods, self-contained: its items, recipes and rules
INTEGRATION_TEMPLATE = {"id": "", "title": "", "bridges": [], "tier": "mid", "why": "",
                        "items": [], "recipes": [], "remove": [], "replace_inputs": []}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    items: int = 0
    recipes: int = 0
    removed: int = 0
    replaced: int = 0
    integrations: int = 0
    bridges: list[str] = field(default_factory=list)
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
    """Integrations' items and rules, then the base rules, then the preset of the chosen difficulty. Items are
    never per preset: an item that exists on easy must exist on hard, or worlds break when the preset changes."""
    out = {k: [] for k in RULE_KEYS}
    items = list(data.get("items", []))
    for ig in data.get("integrations", []):
        items += list(ig.get("items", []))
        for k in RULE_KEYS:
            out[k] += list(ig.get(k, []))
    for k in RULE_KEYS:
        out[k] += list(data.get(k, []))
    preset = data.get("presets", {}).get(data.get("difficulty", "normal"), {})
    for k in RULE_KEYS:
        out[k] += list(preset.get(k, []))
    out["items"] = items
    return out


def recipe_id(r: dict, ns: str, n: int) -> str:
    return r.get("id") or f"{ns}:packloom/{n}"


def own_index(recipes: list[dict], ns: str) -> dict:
    """The pack's own recipes in the registry's shape (id -> {type, result, inputs}), so that remove and
    replace_inputs rules can target them like any mod recipe."""
    own = {}
    for n, r in enumerate(recipes, 1):
        t = r.get("type", "shaped")
        if t == "shaped":
            own[recipe_id(r, ns, n)] = {"type": "minecraft:crafting_shaped", "result": r.get("result"),
                                        "inputs": sorted(set(r.get("key", {}).values()))}
        elif t == "shapeless":
            own[recipe_id(r, ns, n)] = {"type": "minecraft:crafting_shapeless", "result": r.get("result"),
                                        "inputs": sorted(set(r.get("inputs", [])))}
        elif isinstance(r.get("json"), dict):
            j = r["json"]
            own[recipe_id(r, ns, n)] = {"type": j.get("type"), "result": registry._result_of(j),
                                        "inputs": sorted(registry._ids_in(j) - {j.get("type")})}
    return own


def _swap(obj, src: str, dst: str):
    """Replace an ingredient reference inside a raw recipe json: {"item": src} or {"tag": src-without-#}."""
    if isinstance(obj, dict):
        if obj.get("item") == src and not src.startswith("#"):
            obj = dict(obj); obj.pop("item"); obj.pop("tag", None)
            obj["tag" if dst.startswith("#") else "item"] = dst.lstrip("#")
            return obj
        if src.startswith("#") and obj.get("tag") == src[1:]:
            obj = dict(obj); obj.pop("tag"); obj.pop("item", None)
            obj["tag" if dst.startswith("#") else "item"] = dst.lstrip("#")
            return obj
        return {k: _swap(v, src, dst) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_swap(v, src, dst) for v in obj]
    return obj


def bake(eff: dict, idx: dict, ns: str) -> dict:
    """Rules that target the pack's own recipes are applied here, at generation time, instead of being left to
    KubeJS: a removed own recipe is not written, a replaced input is swapped in the recipe itself. Rules that
    also hit mod recipes stay in the script for that part. The result has the same keys as `eff`."""
    recipes = [json.loads(json.dumps(r)) for r in eff["recipes"]]
    own = own_index(recipes, ns)
    ids = [recipe_id(r, ns, n) for n, r in enumerate(recipes, 1)]
    dropped = set()
    keep_remove = []
    for rm in eff["remove"]:
        try:
            dropped |= set(registry.match_recipes(own, rm))
            if registry.recipes_matching(idx, rm):
                keep_remove.append(rm)
        except ValueError:
            keep_remove.append(rm)
    keep_replace = []
    for rp in eff["replace_inputs"]:
        src, dst, where = rp.get("from", ""), rp.get("to", ""), rp.get("in", {})
        try:
            own_hits = [h for h in registry.match_recipes(own, where) if src in own[h]["inputs"]]
            reg_hits = [h for h in registry.recipes_matching(idx, where) if src in idx["recipe"][h]["inputs"]]
        except ValueError:
            keep_replace.append(rp); continue
        for h in own_hits:
            r = recipes[ids.index(h)]
            if r.get("type", "shaped") == "shaped":
                r["key"] = {k: (dst if v == src else v) for k, v in r["key"].items()}
            elif r.get("type") == "shapeless":
                r["inputs"] = [dst if v == src else v for v in r["inputs"]]
            else:
                r["json"] = _swap(r["json"], src, dst)
        if reg_hits:
            keep_replace.append(rp)
    out = dict(eff)
    out["recipes"] = [r for r, i in zip(recipes, ids) if i not in dropped]
    out["remove"], out["replace_inputs"] = keep_remove, keep_replace
    return out


# ---------- validation ----------

class Checker:
    def __init__(self, idx: dict, declared: set[str], report: Report):
        self.idx, self.declared, self.report = idx, declared, report
        # every block has an item form (the handful of technical blocks are never crafted); vanilla blocks come
        # from the server jar's lang file, which lists them as blocks only
        self.known_items = set(idx["item"]) | set(idx.get("block", {})) | declared
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


def _custom_refs(obj, under: Optional[str] = None) -> tuple[set[str], set[str]]:
    """(items, item tags) referenced by a raw recipe json. A `tag` under a fluid or chemical key is not an item
    tag and is left alone; bare strings (fluid ids, chemical ids, sounds) are never checked."""
    items, tags = set(), set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "item" and isinstance(v, str):
                items.add(v)
            elif k == "tag" and isinstance(v, str):
                if under not in NON_ITEM_KEYS and not any(x in obj for x in ("fluid", "gas", "infuse_type", "pigment", "slurry", "amount")):
                    tags.add("#" + v)
            else:
                i, t = _custom_refs(v, k if k in NON_ITEM_KEYS else under)
                items |= i; tags |= t
    elif isinstance(obj, list):
        for v in obj:
            i, t = _custom_refs(v, under)
            items |= i; tags |= t
    return items, tags


def check(data: dict, idx: dict) -> Report:
    rep = Report()
    ns = data.get("namespace", "")
    eff = effective(data)
    declared = set()
    for it in eff["items"]:
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
        if iid in declared:
            rep.errors.append(f"item {iid}: declared twice")
        declared.add(iid)
    rep.items = len(declared)
    ck = Checker(idx, declared, rep)

    seen_ids = set()
    for n, r in enumerate(eff["recipes"], 1):
        where = f"recipe #{n}" + (f" ({r['id']})" if r.get("id") else "")
        if r.get("id"):
            if r["id"] in seen_ids:
                rep.errors.append(f"{where}: recipe id used twice")
            seen_ids.add(r["id"])
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
                items, tags = _custom_refs(r["json"])
                for ref in sorted(items):
                    ck.item(ref, f"{where} json")
                for ref in sorted(tags):
                    if ref not in ck.known_tags:
                        rep.warnings.append(f"{where} json: {ref} is not an item tag in the registry (a fluid or chemical tag is fine)")
        else:
            rep.errors.append(f"{where}: type must be shaped, shapeless or custom")
    own = own_index(eff["recipes"], ns)

    for n, rm in enumerate(eff["remove"], 1):
        where = f"remove #{n}"
        if not isinstance(rm, dict) or not rm:
            rep.errors.append(f"{where}: must be an object like {{\"id\": \"ns:path\"}} or {{\"output\": \"ns:item\"}}"); continue
        try:
            hits = registry.recipes_matching(idx, rm)
            mine = registry.match_recipes(own, rm)
        except ValueError as e:
            rep.errors.append(f"{where}: {e}"); continue
        if not hits and not mine:
            rep.errors.append(f"{where}: no recipe matches {json.dumps(rm)}")
        if hits:
            rep.notes.append(f"{where}: removes {len(hits)} recipe(s): {', '.join(hits[:5])}{'…' if len(hits) > 5 else ''}")
            rep.removed += len(hits)
        if mine:
            rep.notes.append(f"{where}: drops {len(mine)} of the pack's own recipe(s) at build time: {', '.join(mine[:5])}")

    for n, rp in enumerate(eff["replace_inputs"], 1):
        where = f"replace_inputs #{n}"
        src, dst, where_filter = rp.get("from", ""), rp.get("to", ""), rp.get("in", {})
        ck.item(src, f"{where} from"); ck.item(dst, f"{where} to")
        try:
            hits = [h for h in registry.recipes_matching(idx, where_filter) if src in idx["recipe"][h]["inputs"]]
            mine = [h for h in registry.match_recipes(own, where_filter) if src in own[h]["inputs"]]
        except ValueError as e:
            rep.errors.append(f"{where}: {e}"); continue
        if not hits and not mine:
            rep.errors.append(f"{where}: no recipe matching {json.dumps(where_filter)} uses {src}")
        if hits:
            rep.notes.append(f"{where}: {src} -> {dst} in {len(hits)} recipe(s): {', '.join(hits[:5])}{'…' if len(hits) > 5 else ''}")
            rep.replaced += len(hits)
            odd = [h for h in hits if idx["recipe"][h].get("type") not in EDITABLE_TYPES]
            for h in odd:
                rep.warnings.append(f"{where}: {h} has type {idx['recipe'][h].get('type')}, which KubeJS may not be able to edit; "
                                    f"`tune verify` after the server run tells")
        if mine:
            rep.notes.append(f"{where}: {src} -> {dst} baked into {len(mine)} of the pack's own recipe(s): {', '.join(mine[:5])}")

    mods = registry.namespaces(idx)
    pairs = set()
    seen_ig = set()
    for n, ig in enumerate(data.get("integrations", []), 1):
        where = f"integration #{n}" + (f" ({ig['id']})" if ig.get("id") else "")
        if not ig.get("id") or not ig.get("title"):
            rep.errors.append(f"{where}: needs an id and a title")
        if ig.get("id") in seen_ig:
            rep.errors.append(f"{where}: id used twice")
        seen_ig.add(ig.get("id"))
        bridges = ig.get("bridges", [])
        if len(bridges) < 2:
            rep.errors.append(f"{where}: `bridges` must name at least two mods")
        for m in bridges:
            if m not in mods:
                rep.warnings.append(f"{where}: bridge mod {m!r} defines no item in the registry (not in the pack, or a typo?)")
        if ig.get("tier", "mid") not in TIERS_OF_PLAY:
            rep.errors.append(f"{where}: tier must be one of {', '.join(TIERS_OF_PLAY)}")
        if not any(ig.get(k) for k in ("items",) + RULE_KEYS):
            rep.errors.append(f"{where}: has no items, recipes or rules")
        for a in bridges:
            for b in bridges:
                if a < b:
                    pairs.add(f"{a}+{b}")
    rep.integrations = len(data.get("integrations", []))
    rep.bridges = sorted(pairs)
    baked = bake(eff, idx, ns)
    rep.recipes = len(baked["recipes"])
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
    elif shape == "dust":                      # a heap
        for y in range(7, 14):
            w = (y - 6) * 5 // 7 + 1
            for x in range(8 - w, 8 + w):
                put(x, y, light if (x * 7 + y * 3) % 5 == 0 else dark if y == 13 else base)
    elif shape == "plate":                     # a flat square with a bevel
        for y in range(4, 12):
            for x in range(3, 13):
                put(x, y, light if (y == 4 or x == 3) else dark if (y == 11 or x == 12) else base)
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
    ns = data.get("namespace", "mypack")
    eff = bake(effective(data), idx, ns)
    kube = pack.overrides / "kubejs"
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


def describe_recipe(r: dict) -> str:
    """One line a person can read: inputs -> result, the machine for custom recipes."""
    t = r.get("type", "shaped")
    if t == "shaped":
        return f"{' + '.join(sorted(set(r.get('key', {}).values())))} -> {r.get('result')}" + (f" x{r['count']}" if r.get("count", 1) != 1 else "") + " (crafting, shaped)"
    if t == "shapeless":
        return f"{' + '.join(r.get('inputs', []))} -> {r.get('result')}" + (f" x{r['count']}" if r.get("count", 1) != 1 else "") + " (crafting)"
    j = r.get("json", {})
    ins = sorted(registry._ids_in(j) - {j.get("type")} - {registry._result_of(j)})
    out = registry._result_of(j) or "?"
    res = j.get("result") if isinstance(j.get("result"), list) else None
    if res and isinstance(res[0], dict) and res[0].get("count", 1) != 1:
        out += f" x{res[0]['count']}"
    elif isinstance(j.get("output"), dict) and j["output"].get("count", 1) != 1:
        out += f" x{j['output']['count']}"
    return f"{' + '.join(ins)} -> {out} ({j.get('type')})"


def doc(data: dict) -> str:
    """INTEGRATIONS.md: every bridge between mods, its items and recipes, readable without the json."""
    igs = data.get("integrations", [])
    names = {it["id"]: it.get("name", it["id"]) for ig in igs for it in ig.get("items", [])}
    names.update({it["id"]: it.get("name", it["id"]) for it in data.get("items", [])})
    pairs: dict[str, list[str]] = {}
    for ig in igs:
        b = ig.get("bridges", [])
        for a in b:
            for c in b:
                if a < c:
                    pairs.setdefault(f"{a} + {c}", []).append(ig.get("title", ig.get("id", "")))
    lines = [f"# Integrations: {data.get('namespace', 'pack')}", "",
             f"{len(igs)} integrations, {len(pairs)} mod pairs bridged, {len(names)} pack-only items. Generated by "
             "`packloom tune doc` from tune.json.", "",
             "| Mods | Integrations |", "|---|---|"]
    lines += [f"| {k} | {', '.join(v)} |" for k, v in sorted(pairs.items())]
    for tier in TIERS_OF_PLAY:
        group = [ig for ig in igs if ig.get("tier", "mid") == tier]
        if not group:
            continue
        lines += ["", f"## {tier.capitalize()} game", ""]
        for ig in group:
            lines.append(f"### {ig.get('title', ig.get('id'))}  `{ig.get('id', '')}`")
            lines.append("")
            lines.append(f"Bridges {' and '.join(ig.get('bridges', []))}. {ig.get('why', '')}".strip())
            lines.append("")
            for it in ig.get("items", []):
                kind = it.get("type", "basic") + (f", {it['tier']} tier" if it.get("tier") else "")
                lines.append(f"- **{it.get('name', it['id'])}** `{it['id']}` ({kind})" + (": " + "; ".join(it.get("tooltip", [])) if it.get("tooltip") else ""))
            for r in ig.get("recipes", []):
                lines.append(f"- {describe_recipe(r)}")
            for rm in ig.get("remove", []):
                lines.append(f"- removes {json.dumps(rm)}")
            for rp in ig.get("replace_inputs", []):
                lines.append(f"- in {json.dumps(rp.get('in', {}))}: {rp.get('from')} -> {rp.get('to')}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
