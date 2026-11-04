"""Parse options.txt keybinds and render a self-contained HTML keyboard map."""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

VANILLA_KEYS = {"attack", "use", "forward", "left", "back", "right", "jump", "sneak", "sprint", "drop", "inventory",
                "chat", "playerlist", "pickItem", "command", "socialInteractions", "screenshot", "togglePerspective",
                "smoothCamera", "fullscreen", "spectatorOutlines", "swapOffhand", "saveToolbarActivator",
                "loadToolbarActivator", "advancements"}
VANILLA_SHARED = {"attack", "use", "sneak", "sprint", "pickItem"}   # mods bind onto these on purpose (JEI, Jade)
KNOWN_NAMES = {"voice_chat": "voicechat", "voice_chat_group": "voicechat", "mute_microphone": "voicechat",
               "hide_icons": "voicechat", "disable_voice_chat": "voicechat", "push_to_talk": "voicechat", "whisper": "voicechat",
               "voice_chat_settings": "voicechat", "voice_chat_toggle_recording": "voicechat", "voice_chat_adjust_volumes": "voicechat",
               "unmountVehicle": "rftoolsbuilder", "prevDestination": "rftoolsbase", "nextDestination": "rftoolsbase", "openManual": "mcjtylib"}
SKIP_SEGMENTS = {"key", "keys", "keybind", "keybinds", "keybinding", "keybindings", "gui", "options", "category", "categories"}


@dataclass
class Bind:
    name: str          # key.inventory, key.sophisticatedbackpacks.open_backpack
    code: str          # key.keyboard.e, key.mouse.left, key.keyboard.unknown
    modifier: str      # "", SHIFT, CONTROL, ALT (Forge)
    mod: str           # inferred mod id, "minecraft" for vanilla

    @property
    def label(self) -> str:
        tail = self.name.split(".")[-1]
        tail = re.sub(r"([a-z])([A-Z])", r"\1 \2", tail).replace("_", " ")
        return tail[:1].upper() + tail[1:]

    @property
    def bound(self) -> bool:
        return not self.code.endswith(".unknown")

    @property
    def vanilla_shared(self) -> bool:
        return self.mod == "minecraft" and self.name.split(".")[-1] in VANILLA_SHARED


def mod_of(name: str) -> str:
    parts = name.split(".")
    if parts[0] == "key" and len(parts) == 2 and parts[1] in VANILLA_KEYS:
        return "minecraft"
    if name.startswith("key.hotbar.") or name.startswith("key.categories."):
        return "minecraft"
    if len(parts) == 2 and parts[1] in KNOWN_NAMES:
        return KNOWN_NAMES[parts[1]]
    for seg in parts:
        if seg.lower() in SKIP_SEGMENTS:
            continue
        if len(parts) <= 2:                 # `gui.xaero_open_map`: the mod hides in the first word
            seg = re.split(r"[_\-]", seg)[0]
        return seg.lower() or "other"
    return "other"


def parse_options(text: str) -> list[Bind]:
    binds = []
    for line in text.splitlines():
        if not line.startswith("key_"):
            continue
        name, _, rest = line[4:].partition(":")
        code, _, modifier = rest.partition(":")
        binds.append(Bind(name=name, code=code.strip(), modifier=modifier.strip().upper(), mod=mod_of(name)))
    return binds


def conflicts(binds: list[Bind]) -> dict[str, list[Bind]]:
    by_key = defaultdict(list)
    for b in binds:
        if b.bound:
            by_key[(b.code, b.modifier)].append(b)
    return {f"{code}{'+' + mod if mod else ''}": v for (code, mod), v in by_key.items() if len(v) > 1}


def summary(binds: list[Bind]) -> dict:
    per_mod = defaultdict(int)
    for b in binds:
        per_mod[b.mod] += 1
    c = conflicts(binds)
    hard = {k: [b.name for b in v] for k, v in c.items() if not any(b.vanilla_shared for b in v)}
    soft = {k: [b.name for b in v] for k, v in c.items() if any(b.vanilla_shared for b in v)}
    return {"total": len(binds), "bound": sum(b.bound for b in binds), "unbound": sum(not b.bound for b in binds),
            "mods": dict(sorted(per_mod.items(), key=lambda kv: -kv[1])),
            "conflicts": hard, "shared_with_vanilla": soft}


# ---------- pack notes: layout overrides, stages, "when is this key needed" ----------
DEFAULT_STAGES = [{"id": "always", "title": "Always"}, {"id": "gui", "title": "In menus"}, {"id": "item", "title": "With an item"},
                  {"id": "late", "title": "Late game"}, {"id": "server", "title": "With friends"}, {"id": "video", "title": "Video"},
                  {"id": "off", "title": "Unbound"}]


def load_notes(path: Optional[Path]) -> dict:
    if not path or not path.exists():
        return {"layout": {}, "stages": DEFAULT_STAGES, "mods": {}, "binds": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("layout", {}); data.setdefault("mods", {}); data.setdefault("binds", {})
    data.setdefault("stages", DEFAULT_STAGES)
    return data


def annotate(binds: list[Bind], notes: dict) -> list[dict]:
    """Bind -> dict for the page, with stage/when/title from notes (bind level wins over mod level)."""
    out = []
    for b in binds:
        mod_note = notes["mods"].get(b.mod, {})
        note = notes["binds"].get(b.name, {})
        stage = note.get("stage") or mod_note.get("stage") or ("always" if b.mod == "minecraft" else "item")
        if not b.bound:
            stage = "off"
        out.append(asdict(b) | {"label": note.get("title") or b.label, "shared": b.vanilla_shared, "stage": stage,
                                "when": note.get("when") or mod_note.get("when") or "",
                                "mod_title": mod_note.get("title") or b.mod})
    return out


def apply_layout(options_text: str, layout: dict) -> tuple[str, list[str]]:
    """Rewrite `key_<id>:<code>` lines according to layout; ids absent from the file are appended. Returns (text, changed ids)."""
    changed, seen = [], set()
    lines = options_text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("key_"):
            continue
        name = line[4:].split(":", 1)[0]
        if name in layout:
            seen.add(name)
            new = f"key_{name}:{layout[name]}"
            if new != line:
                lines[i] = new
                changed.append(name)
    for name, code in layout.items():
        if name not in seen:
            lines.append(f"key_{name}:{code}")
            changed.append(name)
    return "\n".join(lines) + "\n", changed



# Mac ANSI layout; each key: (options.txt code suffix, label, width units)
ROWS = [
    [("escape", "esc", 1.3)] + [(f"f{i}", f"F{i}", 1) for i in range(1, 13)],
    [("grave.accent", "`", 1), ("1", "1", 1), ("2", "2", 1), ("3", "3", 1), ("4", "4", 1), ("5", "5", 1), ("6", "6", 1),
     ("7", "7", 1), ("8", "8", 1), ("9", "9", 1), ("0", "0", 1), ("minus", "-", 1), ("equal", "=", 1), ("backspace", "delete", 1.6)],
    [("tab", "tab", 1.6), ("q", "Q", 1), ("w", "W", 1), ("e", "E", 1), ("r", "R", 1), ("t", "T", 1), ("y", "Y", 1), ("u", "U", 1),
     ("i", "I", 1), ("o", "O", 1), ("p", "P", 1), ("left.bracket", "[", 1), ("right.bracket", "]", 1), ("backslash", "\\", 1)],
    [("caps.lock", "caps", 2), ("a", "A", 1), ("s", "S", 1), ("d", "D", 1), ("f", "F", 1), ("g", "G", 1), ("h", "H", 1), ("j", "J", 1),
     ("k", "K", 1), ("l", "L", 1), ("semicolon", ";", 1), ("apostrophe", "'", 1), ("enter", "return", 1.6)],
    [("left.shift", "shift", 2.5), ("z", "Z", 1), ("x", "X", 1), ("c", "C", 1), ("v", "V", 1), ("b", "B", 1), ("n", "N", 1), ("m", "M", 1),
     ("comma", ",", 1), ("period", ".", 1), ("slash", "/", 1), ("right.shift", "shift", 2.1)],
    [("left.control", "ctrl", 1.3), ("left.alt", "opt", 1.3), ("left.win", "cmd", 1.6), ("space", "", 6.2), ("right.win", "cmd", 1.6),
     ("right.alt", "opt", 1.3), ("left", "←", 1), ("up", "↑", 1), ("down", "↓", 1), ("right", "→", 1)],
]
EXTRA = [("key.mouse.left", "LMB"), ("key.mouse.right", "RMB"), ("key.mouse.middle", "MMB"), ("key.mouse.4", "M4"), ("key.mouse.5", "M5"),
         ("key.keyboard.insert", "ins"), ("key.keyboard.delete", "del"), ("key.keyboard.home", "home"), ("key.keyboard.end", "end"),
         ("key.keyboard.page.up", "pgup"), ("key.keyboard.page.down", "pgdn"), ("key.keyboard.print.screen", "prt"),
         ("key.keyboard.scroll.lock", "scrl"), ("key.keyboard.pause", "pause")] + [(f"key.keyboard.keypad.{i}", f"kp{i}") for i in range(10)]


def render_html(binds: list[Bind], title: str = "Keybinds", notes: Optional[dict] = None) -> str:
    notes = notes or load_notes(None)
    data = {"binds": annotate(binds, notes), "stages": notes["stages"], "intro": notes.get("intro", ""),
            "rows": [[{"code": "key.keyboard." + c, "label": l, "w": w} for c, l, w in row] for row in ROWS],
            "extra": [{"code": c, "label": l, "w": 1.2} for c, l in EXTRA],
            "summary": summary(binds)}
    return TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__DATA__", json.dumps(data, ensure_ascii=False))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f5f0;--card:#fff;--ink:#1f1f1d;--mute:#6b6a64;--line:#dcdad2;--free:#eceae2;--one:#b5d4f4;--one-ink:#0c447c;--many:#f09595;--many-ink:#791f1f;--soft:#fac775;--soft-ink:#633806;--van:#d3d1c7;--sel:#7f77dd}
@media (prefers-color-scheme:dark){:root{--bg:#1b1b19;--card:#242422;--ink:#ecebe4;--mute:#a09f97;--line:#3a3a36;--free:#2e2e2b;--one:#185fa5;--one-ink:#e6f1fb;--many:#a32d2d;--many-ink:#fcebeb;--soft:#854f0b;--soft-ink:#faeeda;--van:#444441}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,system-ui,sans-serif}
header{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;gap:20px;align-items:baseline;flex-wrap:wrap}
h1{font-size:18px;font-weight:500;margin:0}.stat{color:var(--mute)}.stat b{color:var(--ink);font-weight:500}
main{display:grid;grid-template-columns:1fr 300px;gap:16px;padding:16px 20px}@media(max-width:900px){main{grid-template-columns:1fr}}
.kb{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;overflow-x:auto}
.row{display:flex;gap:5px;margin-bottom:5px}.key{height:44px;border-radius:6px;background:var(--free);border:1px solid var(--line);
display:flex;flex-direction:column;justify-content:space-between;padding:3px 5px;font-size:11px;cursor:pointer;position:relative;min-width:0}
.key .l{font-weight:500}.key .n{font-size:10px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.key.one{background:var(--one);color:var(--one-ink)}.key.one .n{color:var(--one-ink)}.key.many{background:var(--many);color:var(--many-ink)}.key.many .n{color:var(--many-ink)}
.key.soft{background:var(--soft);color:var(--soft-ink)}.key.soft .n{color:var(--soft-ink)}.key.van{background:var(--van)}.key.dim{opacity:.25}.key.sel{outline:2px solid var(--sel);outline-offset:1px}
.extra{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line)}
aside{display:flex;flex-direction:column;gap:12px}.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.panel h2{font-size:14px;font-weight:500;margin:0 0 8px}.panel ul{list-style:none;margin:0;padding:0}.panel li{padding:4px 0;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:8px}
.panel li:first-child{border-top:0}.mod{color:var(--mute);font-size:12px}input{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
.mods button{all:unset;cursor:pointer;display:flex;justify-content:space-between;width:100%;padding:4px 0}.mods button.on{color:var(--sel);font-weight:500}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--mute)}.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:4px;border:1px solid var(--line)}
.chip{all:unset;cursor:pointer;border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12px;color:var(--mute)}.chip.on{background:var(--sel);color:#fff;border-color:var(--sel)}
.grp h3{font-size:13px;font-weight:500;margin:10px 0 4px;color:var(--mute)}.grp li{display:block}.grp .k{display:inline-block;min-width:34px;padding:0 5px;border:1px solid var(--line);border-radius:4px;font-size:11px;text-align:center;margin-right:6px;background:var(--free)}.grp .w{color:var(--mute);font-size:12px;display:block;margin-left:46px}
.conf{color:var(--many-ink);background:var(--many);border-radius:6px;padding:2px 6px;font-size:12px;display:inline-block;margin:2px 2px 0 0}
</style></head><body>
<header><h1>__TITLE__</h1><span class="stat"><b id="s-bound"></b> bound</span><span class="stat"><b id="s-unbound"></b> unbound</span>
<span class="stat"><b id="s-conf"></b> conflicts</span><span class="stat"><b id="s-mods"></b> mods</span>
<span class="legend"><span><i class="sw" style="background:var(--free)"></i>free</span><span><i class="sw" style="background:var(--van)"></i>vanilla only</span>
<span><i class="sw" style="background:var(--one)"></i>one mod action</span><span><i class="sw" style="background:var(--soft)"></i>shared with attack/use/sneak</span><span><i class="sw" style="background:var(--many)"></i>conflict</span></span></header>
<div id="intro" style="padding:0 20px;color:var(--mute);max-width:900px"></div>
<div id="stages" style="padding:8px 20px;display:flex;gap:6px;flex-wrap:wrap"></div>
<main><section class="kb" id="kb"></section>
<aside><div class="panel"><input id="q" placeholder="Search action or mod…"></div>
<div class="panel"><h2 id="p-title">Hover a key</h2><ul id="p-list"></ul></div>
<div class="panel"><h2>Conflicts</h2><div id="conf"></div></div>
<div class="panel mods"><h2>Mods</h2><ul id="mods"></ul></div></aside></main>
<section class="panel grp" id="groups" style="margin:0 20px 20px"></section>
<script>
const D=__DATA__;const byKey={};for(const b of D.binds){if(b.code.endsWith('.unknown'))continue;(byKey[b.code]=byKey[b.code]||[]).push(b)}
let filterMod=null,pinned=null,query='',stageOn=new Set(D.stages.map(s=>s.id));const stageTitle=Object.fromEntries(D.stages.map(s=>[s.id,s.title]));
document.getElementById('intro').textContent=D.intro||'';
function cls(code){const bs=byKey[code]||[];if(!bs.length)return'';const mods=new Set(bs.map(b=>b.modifier));
const groups={};for(const b of bs){(groups[b.modifier]=groups[b.modifier]||[]).push(b)}const hard=Object.values(groups).some(g=>g.length>1&&!g.some(b=>b.shared));const soft=Object.values(groups).some(g=>g.length>1&&g.some(b=>b.shared));
if(hard)return'many';if(soft)return'soft';if(bs.every(b=>b.mod==='minecraft'))return'van';return'one'}
function keyEl(k){const d=document.createElement('div');d.className='key '+cls(k.code);d.style.flex=`0 0 ${k.w*44}px`;d.dataset.code=k.code;
const bs=byKey[k.code]||[];d.innerHTML=`<span class="l">${k.label}</span><span class="n">${bs.length?bs.map(b=>b.label).join(', '):''}</span>`;
d.title=bs.map(b=>(b.modifier?b.modifier+'+':'')+b.name).join('\n');d.onmouseenter=()=>{if(!pinned)show(k)};d.onclick=()=>{pinned=pinned===k.code?null:k.code;show(k);paint()};return d}
function show(k){const bs=byKey[k.code]||[];document.getElementById('p-title').textContent=(k.label||'space')+(pinned?' (pinned)':'')+(bs.length?'':' — free');
document.getElementById('p-list').innerHTML=bs.map(b=>`<li><span>${b.modifier?b.modifier+' + ':''}${b.label}${b.when?`<span class="w" style="margin-left:0">${b.when}</span>`:''}</span><span class="mod">${b.mod_title}</span></li>`).join('')}
function matches(code){const bs=byKey[code]||[];if(stageOn.size<D.stages.length&&!bs.some(b=>stageOn.has(b.stage)))return false;if(filterMod&&!bs.some(b=>b.mod===filterMod))return false;if(query&&!bs.some(b=>(b.name+' '+b.label+' '+b.mod).toLowerCase().includes(query)))return false;return true}
function paint(){for(const el of document.querySelectorAll('.key')){el.classList.toggle('dim',(filterMod||query||stageOn.size<D.stages.length)&&!matches(el.dataset.code));el.classList.toggle('sel',pinned===el.dataset.code)}}
const kb=document.getElementById('kb');for(const row of D.rows){const r=document.createElement('div');r.className='row';for(const k of row)r.appendChild(keyEl(k));kb.appendChild(r)}
const ex=document.createElement('div');ex.className='extra';for(const k of D.extra)ex.appendChild(keyEl(k));kb.appendChild(ex);
const S=D.summary;document.getElementById('s-bound').textContent=S.bound;document.getElementById('s-unbound').textContent=S.unbound;
document.getElementById('s-conf').textContent=Object.keys(S.conflicts).length;document.getElementById('s-mods').textContent=Object.keys(S.mods).length;
document.getElementById('conf').innerHTML=Object.entries(S.conflicts).map(([k,v])=>`<div><span class="conf">${k.replace('key.keyboard.','').replace('key.mouse.','mouse ')}</span> ${v.join(', ')}</div>`).join('')||'<span class="mod">none</span>';
document.getElementById('mods').innerHTML=Object.entries(S.mods).map(([m,n])=>`<li><button data-mod="${m}"><span>${m}</span><span class="mod">${n}</span></button></li>`).join('');
for(const b of document.querySelectorAll('.mods button'))b.onclick=()=>{filterMod=filterMod===b.dataset.mod?null:b.dataset.mod;for(const x of document.querySelectorAll('.mods button'))x.classList.toggle('on',x.dataset.mod===filterMod);paint()};
document.getElementById('q').oninput=e=>{query=e.target.value.trim().toLowerCase();paint()};
const st=document.getElementById('stages');for(const s of D.stages){const b=document.createElement('button');b.className='chip on';b.textContent=s.title;b.onclick=()=>{if(stageOn.size===D.stages.length){stageOn=new Set([s.id])}else if(stageOn.has(s.id)){stageOn.delete(s.id);if(!stageOn.size)stageOn=new Set(D.stages.map(x=>x.id))}else stageOn.add(s.id);for(const c of st.children)c.classList.toggle('on',stageOn.has(c.dataset.id));paint()};b.dataset.id=s.id;st.appendChild(b)}
const keyName=c=>c.replace('key.keyboard.','').replace('key.mouse.','mouse ').replace('.accent','').replace('left.','L-').replace('right.','R-');
const groups=document.getElementById('groups');for(const s of D.stages){const items=D.binds.filter(b=>b.stage===s.id);if(!items.length)continue;const h=document.createElement('h3');h.textContent=s.title+' · '+items.length;groups.appendChild(h);const ul=document.createElement('ul');
for(const b of items.sort((a,b)=>(a.mod+a.label).localeCompare(b.mod+b.label))){const li=document.createElement('li');li.innerHTML=`<span class="k">${b.code.endsWith('.unknown')?'—':(b.modifier?b.modifier.toLowerCase()+'+':'')+keyName(b.code)}</span>${b.label} <span class="mod">${b.mod_title}</span>${b.when?`<span class="w">${b.when}</span>`:''}`;ul.appendChild(li)}groups.appendChild(ul)}
</script></body></html>
"""
