# Icons: 16×16 textures as text

Pack-only items (tune.json) need icons that sit next to the mods' own items without looking foreign. packloom
keeps them as text in `icons.json` and renders PNGs with stdlib Python; the skill `/pack-icons` holds the
drawing rules. The pieces:

- **Ramp.** `material` (metal, gem, dust, wood, cloth, energy, stone) and `color` give six shades: `o` outline,
  `D` dark, `M` the colour, `L` light, `H` highlight, `S` specular. Shadows are pulled toward blue and
  saturated, lights toward yellow and paler, the way the mods' artists shade; the outline is the material's
  darkest shade, not black. `pixel.ramp("#ca6b1a", "metal")` reproduces DivineRPG's realmite ingot palette
  within a few steps per channel.
- **Grid.** 16 rows of 16 letters, `.` transparent. `extra` adds letters for a second material (osmium trim
  as greys `1`..`4`), glints (`Y`), sparks (`F`); handles use the built-in vanilla wood `a w h g`.
- **References.** `icons grid ns:name` prints any texture from the vanilla client jar, `server/mods` or
  `overrides/mods` as letters with a legend. `icons adapt ref name --color --material` turns it into a ramp
  grid (brightness bins, greys kept) and writes the entry: the silhouette, handle angle and light direction
  of the mod's own item, ready to recolour and detail.
- **Sheet.** `icons sheet mine ref1 ref2 --out sheet.png` scales everything ×8 on a checkerboard so the
  result is looked at next to its parents before shipping. The agent reads the PNG and fixes the grid.
- **Borrowing.** A texture that exists in a jar but has no item (DivineRPG ships `realmite_dust.png`) is
  used directly: tune.json `"icon": {"texture": "divinerpg:item/realmite_dust"}` becomes KubeJS
  `.texture(...)`, no PNG is drawn.

`icons build` overwrites the PNGs (icons.json is the source); `tune build` writes a placeholder only where
no PNG exists. Worn armour textures, block textures and animated textures are not generated yet; the skill
says what to do by hand.

TechPack 1.3.0: nine icons adapted from DivineRPG's realmite tools and arlemite armour, Thermal's plate and
Mekanism's osmium, three dusts borrowed from DivineRPG.
