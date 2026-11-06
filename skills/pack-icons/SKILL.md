---
name: pack-icons
description: Draw 16x16 item icons and textures for a pack's own items (tune.json) in the style of the mods they bridge, as text grids in icons.json that packloom renders to PNG, with reference textures pulled from the pack's jars for comparison. Use when a pack-only item has a placeholder icon, when a user says an icon looks weak or off-style, or asks for a texture, icon, sprite or armour look for a KubeJS item.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *), Read, Write, Edit
---

# Icons for pack-only items

An icon that looks drawn by someone else than the mod next to it is worse than no icon. The bar is the
mod's own art: open the textures of the items the new item is made from, draw in their palette, their
silhouette and their light, and look at the result next to them before shipping. Everything here is text
(`icons.json` next to `tune.json`) and stdlib Python; no image editor.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py icons grid divinerpg:realmite_ingot thermal:bronze_plate_0   # a texture as letters + legend
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py icons adapt divinerpg:realmite_sword techpack:flux_blade --color "#d4621c" --material metal
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py icons build                                                  # icons.json -> textures/item/*.png
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py icons sheet techpack:flux_blade divinerpg:realmite_sword --out sheet.png   # look at it (Read the PNG)
```

References are looked up as `ns:name` (= `ns:item/name`) or `ns:item/materials/flux_ingot` inside the vanilla
client jar (Prism), `server/mods/*.jar` and `overrides/mods/*.jar`. Run `/pack-build` with `--server` first
so the jars are there.

## icons.json

```json
{ "icons": [
  { "name": "techpack:fluxed_realmite_ingot", "material": "metal", "color": "#d4621c",
    "extra": {"Y": "#f7e16b", "F": "#ffffff"}, "outline": false,
    "grid": ["................", "..........DD....", "..." ] } ] }
```

- `material` metal | gem | dust | wood | cloth | energy | stone and `color` give the **ramp**: six letters
  `o` outline, `D` dark, `M` the colour itself, `L` light, `H` highlight, `S` specular. Shadows go cooler and
  more saturated, lights warmer and paler, the outline is the darkest shade of the material. Never type the
  shades by hand; change `color` or `material` instead.
- `extra` adds letters: a second material on the same icon (osmium trim on green armour: `"1".."4"` greys),
  energy glints (`Y`), a white spark (`F`). Wood for handles is built in: `a w h g` dark to light.
- `handle: [first_row, last_row, x_at_first_row]` paints a 3 px 45° grip (vanilla's angle) before the outline.
- `outline: true` (default) draws `o` around every opaque pixel; set `false` when the grid already has its
  outline, which every adapted reference does.
- `.` is transparent. 16 rows of 16 characters, or `icons build` refuses the icon.

`icons build` overwrites the PNGs: icons.json is the source. `tune build` writes a placeholder only where no
PNG exists, so the two never fight. An item can also borrow a texture that exists in a jar but is unused by
its mod (DivineRPG ships `realmite_dust.png` without a dust item): in tune.json
`"icon": {"texture": "divinerpg:item/realmite_dust"}` and no PNG is drawn at all. Look for such textures
first: `unzip -l server/mods/<mod>.jar | grep textures/item`.

## How to draw one

1. **Find the parents.** The item bridges two mods; pick the texture it should sit next to in JEI: the ingot
   it is made from, the mod's tool of the same kind, the armour piece of the same slot. `icons grid` both.
2. **Start from a silhouette, not a blank.** `icons adapt <ref> <name> --color --material` turns the
   reference into a ramp grid (brightness → `o D M L H S`, greys kept as digits) and writes the entry. A
   pickaxe adapted from the mod's pickaxe keeps the handle angle, the head shape and where the light falls.
   For a shape no mod has, draw it from the closest vanilla item (`minecraft:iron_ingot`, `minecraft:redstone`,
   `minecraft:iron_sword`, `minecraft:iron_helmet`) at the same scale: ingots are 14 px wide and 10 tall, tools
   run corner to corner, armour sits in the middle 12 columns.
3. **Make it this item.** What says "fluxed", "osmic", "void"? Two or three pixels, placed where the light
   already is: glints along the lit top face, a core line down a blade, an inlay in the centre of a plate, trim
   of the second material where the reference has its trim. Not a tint of the whole thing, not noise.
4. **Build and look.** `icons build`, then `icons sheet <mine> <parent1> <parent2> --out sheet.png` and Read
   the PNG. Judge side by side: same darkness of outline, same number of shades (4-6 per material), light from
   the top-left, specular on metal and gems only, the new item neither brighter nor more saturated than its
   parents unless it is an energy item. Fix the grid, build again. Two rounds is normal; one is rare.
5. Rebuild the pack (`/pack-build`) and sync the instance; icons are client assets, the server test does
   not see them. Check in game once per batch: the first-person tool, the hotbar, and the worn armour.

## What makes it look amateur

- Pure black or grey outlines on a coloured item (vanilla's are the material's darkest shade).
- Pillow shading: light in the middle, darker toward every edge. Light comes from the top-left, one side only.
- Symmetric blobs; vanilla ingots, dust heaps and gems are asymmetric.
- Hue-identical ramps (the same colour lighter and darker): shadows should be bluer, lights yellower.
- More than six colours per material, single-pixel noise outside dust, anti-aliased edges.
- A tool whose handle is not at 45°, a sword whose blade is 1 px, armour drawn in a 16-px box but with a
  different thickness than vanilla's 1-px edge.
- Recolouring a whole reference and calling it new: change silhouette or detail too, or players will
  think it is the old item.

## Worn armour, blocks, animated textures

- KubeJS 1.20.1 renders a custom armour item with its tier's worn texture (netherite for `tier: netherite`).
  A custom look needs an armour tier registered with `ItemEvents.armorTierRegistry` and two 64x32 layer
  files; the lookup path differs between sources, so put the files at
  `kubejs/assets/kubejs/textures/models/armor/<tier>_layer_1.png` and `_layer_2.png`, name the tier without a
  namespace, and verify in game. Not supported by tune.json yet; leave the tier at netherite unless asked.
- Blocks need `textures/block/` plus a model; packloom does not generate those yet.
- Animated textures are 16 x N frames with a `.png.mcmeta`; `icons sheet` shows the first frame.

## Credit

A grid adapted from a mod's texture is derived art. Fine inside a pack for friends and for a private server;
before publishing a pack on Modrinth, redraw the silhouette (step 3 with real changes) or check the mod's
licence (DivineRPG and Thermal are source-available with all-rights-reserved assets; Mekanism is MIT).
