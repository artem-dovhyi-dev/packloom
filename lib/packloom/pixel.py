"""Pixel art for pack-only items: 16x16 PNG in the vanilla style, stdlib only.

An icon is text: a 16-row grid of palette letters (`.` transparent) plus a material and a base colour from
which a hue-shifted ramp is derived (outline `o`, dark `D`, mid `M`, light `L`, highlight `H`, specular `S`).
`icons.json` next to tune.json holds every icon; `icons build` renders them into
overrides/kubejs/assets/<ns>/textures/item/. `icons sheet` lays the pack's icons next to reference textures
pulled out of the pack's own jars, scaled up, so the result can be looked at and compared before shipping.
"""
from __future__ import annotations

import colorsys
import json
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Iterable, Optional

Pixels = list[list[tuple]]          # rows of (r, g, b, a)
RAMP = "oDMLHS"
MATERIALS = {
    #           value of dark / light vs base, saturation of dark, hue pulled toward (deg) in shadow / light, specular dot
    "metal":   {"dark": 0.58, "light": 1.16, "sat": 1.08, "hue_dark": 250, "hue_light": 55, "spec": True},
    "gem":     {"dark": 0.52, "light": 1.25, "sat": 1.15, "hue_dark": 260, "hue_light": 60, "spec": True},
    "dust":    {"dark": 0.66, "light": 1.14, "sat": 1.00, "hue_dark": 250, "hue_light": 50, "spec": False},
    "wood":    {"dark": 0.64, "light": 1.18, "sat": 1.00, "hue_dark": 20, "hue_light": 45, "spec": False},
    "cloth":   {"dark": 0.68, "light": 1.18, "sat": 0.95, "hue_dark": 250, "hue_light": 50, "spec": False},
    "energy":  {"dark": 0.52, "light": 1.30, "sat": 1.25, "hue_dark": 280, "hue_light": 55, "spec": True},
    "stone":   {"dark": 0.66, "light": 1.18, "sat": 0.90, "hue_dark": 240, "hue_light": 50, "spec": False},
}


# ---------- colour ----------

def hex_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def rgb_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb[:3])


def _shift(rgb, value: float, sat: float, toward_hue: float, amount: float) -> tuple[int, int, int]:
    """Scale value and saturation, then move the hue a fraction of the way toward `toward_hue` degrees."""
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    h = (h * 360) % 360
    d = ((toward_hue - h + 180) % 360) - 180
    h = (h + d * amount) % 360
    v = max(0.0, min(1.0, v * value))
    s = max(0.0, min(1.0, s * sat))
    return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h / 360, s, v))


def ramp(color: str, material: str = "metal") -> dict[str, str]:
    """Six shades a pixel artist would pick by hand: shadows go cooler and more saturated, lights go warmer
    and paler, the outline is the darkest shade of the material, never black."""
    m = MATERIALS[material]
    base = hex_rgb(color)
    dark = _shift(base, m["dark"], m["sat"], m["hue_dark"], 0.08)
    out = _shift(base, m["dark"] * 0.72, m["sat"] * 1.05, m["hue_dark"], 0.12)
    light = _shift(base, m["light"], 0.92, m["hue_light"], 0.10)
    high = _shift(base, m["light"] * 1.10, 0.70, m["hue_light"], 0.22)
    spec = _shift(high, 1.25, 0.30, m["hue_light"], 0.1) if m["spec"] else high
    return {"o": rgb_hex(out), "D": rgb_hex(dark), "M": rgb_hex(base), "L": rgb_hex(light),
            "H": rgb_hex(high), "S": rgb_hex(spec)}


# ---------- grids ----------

def parse_grid(rows: Iterable[str], size: int = 16) -> list[list[str]]:
    g = [list(r) for r in rows]
    if len(g) != size or any(len(r) != size for r in g):
        raise ValueError(f"grid must be {size} rows of {size} characters")
    return g


def outline(g: list[list[str]], letter: str = "o") -> None:
    """Dark edge around every opaque pixel (4-neighbour), the vanilla item look."""
    n = len(g)
    opaque = [(x, y) for y in range(n) for x in range(n) if g[y][x] != "."]
    for x, y in opaque:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < n and 0 <= ny < n and g[ny][nx] == ".":
                g[ny][nx] = letter


def handle(g: list[list[str]], first_row: int, last_row: int, x_at_first: int,
           dark: str = "w", light: str = "h") -> None:
    """A 3 px wide 45-degree grip from (x_at_first, first_row) down-left to last_row: vanilla tools hold
    their handle at exactly this angle, darker wood on the lower-left cell, lighter on the upper-right."""
    n = len(g)
    for r in range(first_row, last_row + 1):
        x = x_at_first - (r - first_row)
        for dx, letter in ((0, dark), (1, light), (2, "a")):
            if 0 <= x + dx < n:
                g[r][x + dx] = letter


def render(g: list[list[str]], palette: dict[str, str]) -> Pixels:
    out = []
    for row in g:
        line = []
        for ch in row:
            if ch == ".":
                line.append((0, 0, 0, 0))
            elif ch not in palette:
                raise KeyError(f"letter {ch!r} is not in the palette {sorted(palette)}")
            else:
                line.append((*hex_rgb(palette[ch]), 255))
        out.append(line)
    return out


def to_grid(px: Pixels, max_letters: int = 46) -> tuple[list[str], dict[str, str]]:
    """The reverse: a texture as rows of letters plus a legend (most frequent colour first), to study
    how a reference was shaded. Darkest colour becomes `o`, then letters a.. by frequency."""
    counts: dict[tuple, int] = {}
    for row in px:
        for p in row:
            if p[3] > 0:
                counts[p[:3]] = counts.get(p[:3], 0) + 1
    if not counts:
        return ["." * len(px[0])] * len(px), {}
    darkest = min(counts, key=lambda c: sum(c))
    order = [darkest] + sorted((c for c in counts if c != darkest), key=lambda c: -counts[c])
    letters = "o" + "abcdefghijklmnpqrstuvwxyzABCEFGIJKNPQRTUVWXYZ"
    legend: dict[tuple, str] = {}
    for i, c in enumerate(order):
        legend[c] = letters[i] if i < len(letters) and i < max_letters else "?"
    rows = ["".join("." if p[3] == 0 else legend[p[:3]] for p in row) for row in px]
    return rows, {v: rgb_hex(k) for k, v in legend.items() if v != "?"}


def adapt(px: Pixels, keep_grey: bool = True) -> tuple[list[str], dict[str, str]]:
    """A reference texture as a ramp grid: every coloured pixel becomes o/D/M/L/H/S by its brightness, so the
    same silhouette and shading re-render in any material and colour. Grey pixels (trim, steel, white
    glints) keep their own colour under digits 1.. so a recolour does not tint them."""
    px = crop16(px)
    cols: dict[tuple, int] = {}
    for row in px:
        for p in row:
            if p[3] > 0:
                cols[p[:3]] = cols.get(p[:3], 0) + 1

    def lum(c):
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def grey(c):
        return max(c) - min(c) < 24

    coloured = [c for c in cols if not (keep_grey and grey(c) and lum(c) > 40)]
    greys = sorted((c for c in cols if c not in coloured), key=lum)
    letter: dict[tuple, str] = {}
    if coloured:
        lo, hi = min(map(lum, coloured)), max(map(lum, coloured))
        for c in coloured:
            t = (lum(c) - lo) / (hi - lo) if hi > lo else 0.5
            letter[c] = "o" if t < 0.12 else "D" if t < 0.36 else "M" if t < 0.62 else "L" if t < 0.80 else "H" if t < 0.94 else "S"
    extra: dict[str, str] = {}
    for i, c in enumerate(greys):
        letter[c] = str(i + 1)[-1] if i < 9 else "9"
        extra[letter[c]] = rgb_hex(c)
    rows = ["".join("." if p[3] == 0 else letter[p[:3]] for p in row) for row in px]
    return rows, extra


# ---------- PNG ----------

def write_png(path: Path, px: Pixels) -> None:
    h, w = len(px), len(px[0])
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_png(data: bytes) -> Pixels:
    """8-bit non-interlaced PNG (grey, RGB, palette, grey+alpha, RGBA) to RGBA rows; what item textures are."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, plte, trns = 8, b"", b"", b""
    w = h = depth = ctype = interlace = 0
    while pos + 8 <= len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        if tag == b"IEND":
            break
        body = data[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat += body
        elif tag == b"PLTE":
            plte = body
        elif tag == b"tRNS":
            trns = body
        pos += 12 + n
    if depth != 8 or interlace:
        raise ValueError(f"unsupported PNG (bit depth {depth}, interlace {interlace})")
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = w * ch
    raw = zlib.decompress(idat)
    rows: list[bytearray] = []
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f, line = raw[p], bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    out: Pixels = []
    for line in rows:
        o = []
        for x in range(w):
            v = line[x * ch:(x + 1) * ch]
            if ctype == 6:
                o.append(tuple(v))
            elif ctype == 2:
                o.append((v[0], v[1], v[2], 255))
            elif ctype == 0:
                o.append((v[0], v[0], v[0], 255))
            elif ctype == 4:
                o.append((v[0], v[0], v[0], v[1]))
            else:
                i = v[0]
                o.append((plte[i * 3], plte[i * 3 + 1], plte[i * 3 + 2], trns[i] if i < len(trns) else 255))
        out.append(o)
    return out


# ---------- references from jars ----------

def find_texture(jars: Iterable[Path], ref: str) -> Optional[Pixels]:
    """`ns:item/name` (or `ns:name`, meaning item/name) looked up as assets/<ns>/textures/<path>.png in the jars."""
    ns, _, path = ref.partition(":")
    if "/" not in path:
        path = "item/" + path
    want = f"assets/{ns}/textures/{path}.png"
    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as z:
                if want in z.namelist():
                    return read_png(z.read(want))
        except zipfile.BadZipFile:
            continue
    return None


def crop16(px: Pixels) -> Pixels:
    """Top-left 16x16 of a texture (animated textures are 16 x N frames; bigger ones are not icons)."""
    return [row[:16] + [(0, 0, 0, 0)] * (16 - len(row[:16])) for row in px[:16]] + \
           [[(0, 0, 0, 0)] * 16] * (16 - len(px[:16]))


# ---------- sheet ----------

def sheet(cells: list[Pixels], scale: int = 8, cols: int = 6, gap: int = 1) -> Pixels:
    """Cells scaled with nearest neighbour on a checkerboard, left to right, top to bottom."""
    rows = max(1, (len(cells) + cols - 1) // cols)
    cell = 16 + gap
    w, h = cols * cell * scale, rows * cell * scale
    bg = (60, 60, 68, 255)
    px = [[bg] * w for _ in range(h)]
    for i, img in enumerate(cells):
        img = crop16(img)
        ox, oy = (i % cols) * cell * scale, (i // cols) * cell * scale
        for y in range(16):
            for x in range(16):
                c = img[y][x]
                if c[3] == 0:
                    c = (84, 84, 92, 255) if (x + y) % 2 else (72, 72, 80, 255)
                elif c[3] < 255:
                    a = c[3] / 255
                    c = tuple(int(c[k] * a + 78 * (1 - a)) for k in range(3)) + (255,)
                for sy in range(scale):
                    for sx in range(scale):
                        px[oy + y * scale + sy][ox + x * scale + sx] = c
    return px


# ---------- icons.json ----------

WOOD = {"a": "#281e0b", "w": "#493615", "h": "#684e1e", "g": "#896727"}   # vanilla tool handles, dark to light

ICON_TEMPLATE = {
    "name": "techpack:example_ingot",
    "material": "metal", "color": "#c8a050",
    "extra": {"Y": "#ffe84a"},
    "handle": [3, 11, 9],
    "grid": ["................"] * 16,
}


def load_icons(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"icons": []}


def build_icon(spec: dict) -> Pixels:
    pal = ramp(spec.get("color", "#8a8aff"), spec.get("material", "metal"))
    pal.update(WOOD)
    pal.update(spec.get("extra", {}))
    g = parse_grid(spec["grid"])
    if spec.get("handle"):
        first, last, x_at_first = spec["handle"]
        handle(g, first, last, x_at_first)
    if spec.get("outline", True):
        outline(g)
    return render(g, pal)


def build_all(pack_dir: Path, overrides: Path, data: dict) -> list[Path]:
    written = []
    for spec in data.get("icons", []):
        ns, _, name = spec["name"].partition(":")
        out = overrides / "kubejs" / "assets" / ns / "textures" / "item" / f"{name}.png"
        write_png(out, build_icon(spec))
        written.append(out.relative_to(pack_dir))
    return written
