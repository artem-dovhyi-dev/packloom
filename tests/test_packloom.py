"""Stdlib unittest; run with: python3 -m unittest discover -s tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from packloom import build, keybinds, triage  # noqa: E402
from packloom.manifest import java_major_for, load_pack, parse_mods  # noqa: E402
from packloom.modrinth import pick_version  # noqa: E402
from packloom.sources import ftb_branch  # noqa: E402


class ManifestTests(unittest.TestCase):
    def test_grammar(self):
        es = parse_mods("# --- x ---\nfoo  # why\nbar@1.2\nbaz client\nftb:ftb-quests-forge\nurl:https://h/m.jar sha256=AB\nmanual:flux # cf\n")
        self.assertEqual([e.key for e in es], ["modrinth:foo", "modrinth:bar", "modrinth:baz", "ftb:ftb-quests-forge",
                                               "url:https://h/m.jar", "manual:flux"])
        self.assertEqual(es[0].comment, "why")
        self.assertEqual(es[1].version, "1.2")
        self.assertEqual(es[2].side, "client")
        self.assertEqual(es[4].sha256, "ab")
        self.assertEqual(es[5].comment, "cf")

    def test_unknown_token_fails(self):
        with self.assertRaises(ValueError):
            parse_mods("foo bogus\n")

    def test_load_pack(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "pack.json").write_text(json.dumps({"name": "P", "version": "1", "minecraft": "1.20.1", "loader": "Forge"}))
            p = load_pack(Path(d))
            self.assertEqual((p.loader, p.loader_version, p.memory_mb, p.java_major), ("forge", "recommended", 4096, 17))

    def test_java_major(self):
        self.assertEqual([java_major_for(v) for v in ("1.16.5", "1.17.1", "1.18.2", "1.20.4", "1.20.5", "1.21.1")],
                         [8, 16, 17, 17, 21, 21])

    def test_ftb_branch(self):
        self.assertEqual(ftb_branch("1.20.1"), "2001")
        self.assertEqual(ftb_branch("1.21"), "2100")


class ModrinthTests(unittest.TestCase):
    def test_pick_version(self):
        found = [{"version_number": "2.0-beta", "version_type": "beta"}, {"version_number": "1.9", "version_type": "release"}]
        self.assertEqual(pick_version(found)["version_number"], "1.9")
        self.assertEqual(pick_version(found, "2.0-beta")["version_number"], "2.0-beta")
        self.assertIsNone(pick_version(found, "3.0"))


class TriageTests(unittest.TestCase):
    def test_mixin_and_missing(self):
        lines = ["[x/ERROR] [mixin/]: Mixin apply for mod lithostitched failed lithostitched.mixins.json:a",
                 "[x/ERROR] [ModSorter/LOADING]: Missing or unsupported mandatory dependencies:",
                 "\tMod ID: 'architectury', Requested by: 'ftbquests', Expected range: '[9,)', Actual version: '[MISSING]'"]
        t = triage.analyze(lines, None, {"ftbquests"})
        self.assertFalse(t.ok)
        self.assertEqual({(s.mod, s.action) for s in t.suspects}, {("lithostitched", "remove"), ("ftbquests", "add-dependency")})

    def test_stacktrace_maps_to_mod_list(self):
        crash = ("\tat net.minecraft.server.Main.main(Main.java:1)\n"
                 "\tat com.example.coolmod.Thing.boom(Thing.java:3)\n"
                 "Mod List:\n| coolmod-1.0.jar | Cool Mod | coolmod | 1.0 | DONE |\n")
        t = triage.analyze(["[x/FATAL] crash"], crash, set())
        self.assertEqual(t.suspects[0].mod, "coolmod")
        self.assertEqual(t.suspects[0].kind, "stacktrace")

    def test_client_ok(self):
        t = triage.analyze(["[Render thread/INFO] [minecraft/SoundEngine]: Sound engine started"], None, set(), client=True)
        self.assertTrue(t.ok)

    def test_ok_server(self):
        t = triage.analyze(["[Server thread/INFO]: Done (12.3s)! For help, type \"help\""])
        self.assertTrue(t.ok)
        self.assertEqual(t.suspects, [])


class KeybindTests(unittest.TestCase):
    def test_parse_and_conflicts(self):
        bs = keybinds.parse_options("key_key.inventory:key.keyboard.e\nkey_key.jade.config:key.keyboard.b\n"
                                    "key_key.sophisticatedbackpacks.open_backpack:key.keyboard.b\nkey_key.spark.x:key.keyboard.unknown\n"
                                    "key_key.hotbar.1:key.keyboard.1\nkey_key.jade.narrate:key.keyboard.b:SHIFT\n")
        self.assertEqual([b.mod for b in bs], ["minecraft", "jade", "sophisticatedbackpacks", "spark", "minecraft", "jade"])
        self.assertEqual([b.mod for b in keybinds.parse_options("key_key.voice_chat:key.keyboard.v\nkey_key.dynamic_fps.toggle:key.keyboard.f\nkey_gui.xaero_open_map:key.keyboard.m\n")], ["voicechat", "dynamic_fps", "xaero"])
        self.assertEqual(keybinds.mod_of("key.prevDestination"), "rftoolsbase")
        s = keybinds.summary(bs)
        self.assertEqual(s["unbound"], 1)
        self.assertEqual(list(s["conflicts"]), ["key.keyboard.b"])   # SHIFT+B is a different chord
        soft = keybinds.summary(keybinds.parse_options("key_key.sneak:key.keyboard.left.shift\nkey_key.jade.show_details:key.keyboard.left.shift\n"))
        self.assertEqual(soft["conflicts"], {})
        self.assertEqual(list(soft["shared_with_vanilla"]), ["key.keyboard.left.shift"])

    def test_apply_layout_and_notes(self):
        text, changed = keybinds.apply_layout("key_key.inventory:key.keyboard.e\nkey_key.x.a:key.keyboard.b\nfoo:bar\n",
                                              {"key.x.a": "key.keyboard.y", "key.new.k": "key.keyboard.k"})
        self.assertEqual(changed, ["key.x.a", "key.new.k"])
        self.assertIn("key_key.x.a:key.keyboard.y", text)
        self.assertIn("key_key.new.k:key.keyboard.k", text)
        self.assertIn("foo:bar", text)
        notes = {"layout": {}, "stages": keybinds.DEFAULT_STAGES, "mods": {"x": {"stage": "late", "when": "later"}},
                 "binds": {"key.x.a": {"stage": "gui", "title": "A!"}}}
        rows = keybinds.annotate(keybinds.parse_options("key_key.x.a:key.keyboard.y\nkey_key.x.b:key.keyboard.unknown\nkey_key.inventory:key.keyboard.e\n"), notes)
        self.assertEqual([(r["stage"], r["label"]) for r in rows], [("gui", "A!"), ("off", "B"), ("always", "Inventory")])
        self.assertEqual(rows[0]["when"], "later")

    def test_render_is_self_contained(self):
        html = keybinds.render_html(keybinds.parse_options("key_key.inventory:key.keyboard.e\n"), "T")
        self.assertIn("<title>T</title>", html)
        self.assertIn('"key.keyboard.e"', html)
        self.assertNotIn("__DATA__", html)


if __name__ == "__main__":
    unittest.main()


class ServerOverridesTests(unittest.TestCase):
    def test_dirs_replaced_files_copied_rest_kept(self):
        from packloom.manifest import Pack
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = Pack(dir=root, name="P", version="1", minecraft="1.20.1", loader="forge")
            (root / "overrides/config/ftbquests/quests").mkdir(parents=True)
            (root / "overrides/config/ftbquests/quests/new.snbt").write_text("new")
            (root / "overrides/config/a.toml").write_text("a=2")
            (root / "server/config/ftbquests/quests").mkdir(parents=True)
            (root / "server/config/ftbquests/quests/old.snbt").write_text("old")
            (root / "server/config/a.toml").write_text("a=1")
            (root / "server/config/mekanism").mkdir()
            (root / "server/config/mekanism/general.toml").write_text("keep")
            build.sync_server_overrides(pack, log=lambda *_: None)
            q = root / "server/config/ftbquests/quests"
            self.assertEqual(sorted(p.name for p in q.iterdir()), ["new.snbt"])
            self.assertEqual((root / "server/config/a.toml").read_text(), "a=2")
            self.assertEqual((root / "server/config/mekanism/general.toml").read_text(), "keep")


from packloom import catalog, hardware, registry, tune  # noqa: E402


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load()

    def test_every_family_has_valid_fields(self):
        for f in self.cat["families"]:
            self.assertTrue(set(f["tags"]) <= set(self.cat["tags"]), f["id"])
            for k, lines in f.get("mods", {}).items():
                self.assertRegex(k, r"^\d+\.\d+(\.\d+)?/(forge|neoforge|fabric|quilt)$")
                parse_mods("\n".join(lines))   # every line is valid mods.txt syntax

    def test_design_picks_defaults_and_wanted(self):
        prop = catalog.design(self.cat, "1.20.1", "forge", ["tech"], tier="high")
        ids = [p.family["id"] for p in prop.picks]
        self.assertIn("thermal", ids); self.assertIn("qol", ids); self.assertIn("perf", ids)
        self.assertNotIn("create", ids)                     # same job as thermal, lower priority
        self.assertIn(("create", "same job as thermal (tech-core); pass --include create to swap"), prop.skipped)
        self.assertNotIn("divinerpg", ids)                  # rpg not wanted

    def test_design_include_swaps_group_and_tier_drops_heavy(self):
        prop = catalog.design(self.cat, "1.20.1", "forge", ["tech", "visual"], tier="low", include=["create"])
        ids = [p.family["id"] for p in prop.picks]
        self.assertIn("create", ids); self.assertNotIn("thermal", ids)
        self.assertNotIn("shaders", ids)                    # heavy on a low tier
        self.assertIn(("shaders", "heavy for a low-tier machine"), prop.skipped)
        self.assertIn("textures", ids)                      # light and default: Faithful ships on every tier
        self.assertIn("balance", ids)

    def test_extras_are_listed_not_picked(self):
        prop = catalog.design(self.cat, "1.20.1", "forge", ["tech", "rpg"], tier="high")
        ids = [p.family["id"] for p in prop.picks]
        self.assertNotIn("ie", ids); self.assertNotIn("aether", ids)         # extras: known, not chosen by a tag
        self.assertIn(("ie", "Immersive Engineering", "tech"), prop.available)
        self.assertLess(len(ids), 20)
        prop = catalog.design(self.cat, "1.20.1", "forge", ["tech"], tier="high", include=["ie"])
        self.assertIn("ie", [p.family["id"] for p in prop.picks])

    def test_design_no_grind_and_avoid(self):
        prop = catalog.design(self.cat, "1.20.1", "forge", ["rpg", "magic"], avoid=["magic"], no_grind=True)
        ids = [p.family["id"] for p in prop.picks]
        self.assertNotIn("divinerpg", ids); self.assertNotIn("botania", ids); self.assertIn("twilight", ids)
        prop = catalog.design(self.cat, "1.20.1", "forge", ["rpg"], no_grind=True, include=["divinerpg"])
        self.assertIn("divinerpg", [p.family["id"] for p in prop.picks])

    def test_unknown_tag_fails(self):
        with self.assertRaises(ValueError):
            catalog.design(self.cat, "1.20.1", "forge", ["bogus"])

    def test_mods_txt_round_trips(self):
        prop = catalog.design(self.cat, "1.20.1", "forge", ["tech", "coop"])
        text = prop.mods_txt("P")
        refs = [e.ref for e in parse_mods(text)]
        self.assertIn("thermal-expansion", refs); self.assertIn("ftb-quests-forge", refs)


class HardwareTests(unittest.TestCase):
    def test_tiers_and_heap(self):
        self.assertEqual(hardware.Hardware(8, "intel").tier, "low")
        self.assertEqual(hardware.Hardware(16, "apple").tier, "mid")
        self.assertEqual(hardware.Hardware(32, "nvidia").tier, "high")
        self.assertEqual(hardware.Hardware(32, "apple").tier, "mid")
        self.assertEqual([hardware.Hardware(r).memory_mb for r in (8, 16, 32, 64)], [3072, 6144, 10240, 10240])

    def test_notes_mention_optifine_on_apple(self):
        self.assertTrue(any("OptiFine" in n for n in hardware.Hardware(16, "apple").notes()))


def _fake_jar(path: Path, files: dict):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for name, body in files.items():
            z.writestr(name, body if isinstance(body, str) else json.dumps(body))


class RegistryTests(unittest.TestCase):
    def test_index_items_tags_recipes(self):
        with tempfile.TemporaryDirectory() as d:
            jar = Path(d, "m.jar")
            _fake_jar(jar, {
                "assets/m/models/item/gear.json": {}, "assets/m/blockstates/box.json": {},
                "assets/m/lang/en_us.json": {"item.m.gear": "Gear", "entity.m.bug": "Bug"},
                "data/m/tags/items/gears.json": {"values": ["m:gear"]},
                "data/m/recipes/gear.json": {"type": "minecraft:crafting_shaped", "pattern": ["#"], "key": {"#": {"tag": "forge:ingots/iron"}}, "result": {"item": "m:gear"}},
                "data/m/recipes/box.json": {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": "m:gear"}], "result": {"item": "m:box", "count": 2}},
                "data/m/dimension/void.json": {}})
            idx = registry.build_index([jar])
            self.assertEqual(idx["item"]["m:gear"], "Gear"); self.assertIn("m:box", {r["result"] for r in idx["recipe"].values()})
            self.assertEqual(idx["entity"]["m:bug"], "Bug"); self.assertEqual(idx["tag"], ["#m:gears"]); self.assertEqual(idx["dimension"], ["m:void"])
            self.assertEqual(idx["recipe"]["m:gear"]["inputs"], ["#forge:ingots/iron"])
            self.assertEqual(registry.recipes_matching(idx, {"mod": "m", "input": "m:gear"}), ["m:box"])
            self.assertEqual(registry.recipes_matching(idx, {"output": "m:gear"}), ["m:gear"])


class TuneTests(unittest.TestCase):
    IDX = {"item": {"a:sword": "", "b:core": "", "minecraft:stick": ""}, "block": {}, "entity": {}, "dimension": [],
           "tag": ["#forge:ingots/iron", "#forge:ingots/gold"], "jars": [],
           "recipe": {"a:sword": {"type": "minecraft:crafting_shaped", "result": "a:sword", "inputs": ["#forge:ingots/iron", "minecraft:stick"]},
                      "b:core": {"type": "minecraft:crafting_shaped", "result": "b:core", "inputs": ["#forge:ingots/gold"]}}}
    DATA = {"namespace": "p", "difficulty": "normal",
            "items": [{"id": "p:blade", "name": "Blade", "type": "sword", "tier": "netherite", "attack_damage_bonus": 4, "rarity": "epic", "glow": True}],
            "recipes": [{"id": "p:blade", "type": "shaped", "pattern": ["A", "B"], "key": {"A": "a:sword", "B": "b:core"}, "result": "p:blade"}],
            "presets": {"hard": {"replace_inputs": [{"in": {"output": "a:sword"}, "from": "#forge:ingots/iron", "to": "#forge:ingots/gold"}],
                                 "remove": [{"output": "b:core"}]}}}

    def test_check_ok_and_presets(self):
        rep = tune.check(self.DATA, self.IDX)
        self.assertTrue(rep.ok, rep.errors); self.assertEqual((rep.items, rep.recipes, rep.replaced, rep.removed), (1, 1, 0, 0))
        rep = tune.check(dict(self.DATA, difficulty="hard"), self.IDX)
        self.assertTrue(rep.ok, rep.errors); self.assertEqual((rep.replaced, rep.removed), (1, 1))

    def test_check_catches_unknown_ids_with_hints(self):
        bad = json.loads(json.dumps(self.DATA)); bad["recipes"][0]["key"]["A"] = "a:swrod"
        rep = tune.check(bad, self.IDX)
        self.assertFalse(rep.ok); self.assertIn("did you mean a:sword", rep.errors[0])
        bad = json.loads(json.dumps(self.DATA)); bad["recipes"][0]["pattern"] = ["AX"]
        self.assertIn("key has no entry", tune.check(bad, self.IDX).errors[0])
        bad = json.loads(json.dumps(self.DATA)); bad["presets"]["hard"]["replace_inputs"][0]["from"] = "#forge:ingots/gold"; bad["difficulty"] = "hard"
        self.assertTrue(any("no recipe matching" in e for e in tune.check(bad, self.IDX).errors))
        bad = json.loads(json.dumps(self.DATA)); bad["items"][0]["id"] = "a:sword"
        self.assertTrue(any("already exists" in e for e in tune.check(bad, self.IDX).errors))

    def test_scripts(self):
        eff = tune.effective(dict(self.DATA, difficulty="hard"))
        js = tune.startup_script(eff["items"])
        self.assertIn('event.create("p:blade", "sword").tier("netherite").attackDamageBonus(4.0).displayName("Blade").rarity("epic").glow(true)', js)
        js = tune.server_script(eff)
        self.assertIn('event.shaped(Item.of("p:blade", 1), ["A", "B"], {"A": "a:sword", "B": "b:core"}).id("p:blade")', js)
        self.assertIn('event.replaceInput({output: "a:sword"}, "#forge:ingots/iron", "#forge:ingots/gold")', js)
        self.assertIn('event.remove({output: "b:core"})', js)

    def test_build_writes_scripts_and_icon(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "pack.json").write_text(json.dumps({"name": "P", "version": "1", "minecraft": "1.20.1", "loader": "forge"}))
            pack = load_pack(Path(d))
            rep = tune.build(pack, self.IDX, self.DATA)
            self.assertTrue(rep.ok)
            self.assertTrue((pack.overrides / "kubejs" / "server_scripts" / "packloom.tune.js").exists())
            png = pack.overrides / "kubejs" / "assets" / "p" / "textures" / "item" / "blade.png"
            self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            stamp = png.stat().st_mtime_ns
            tune.build(pack, self.IDX, self.DATA)
            self.assertEqual(png.stat().st_mtime_ns, stamp)   # an existing texture is never overwritten


class IntegrationTests(unittest.TestCase):
    IDX = json.loads(json.dumps(TuneTests.IDX))
    IDX["item"].update({"c:ore": "", "c:ingot": "", "a:gear": ""})
    DATA = {"namespace": "p", "difficulty": "normal",
            "integrations": [
                {"id": "dust", "title": "A pulverizes C", "bridges": ["a", "c"], "tier": "early", "why": "ore doubling",
                 "items": [{"id": "p:c_dust", "name": "C Dust", "icon": {"shape": "dust", "color": "#aabbcc"}}],
                 "recipes": [{"id": "p:c_dust", "type": "custom", "json": {"type": "a:pulverizer", "ingredient": {"item": "c:ore"},
                                                                          "result": [{"item": "p:c_dust", "count": 2}]}},
                             {"id": "p:c_smelt", "type": "custom", "json": {"type": "minecraft:smelting", "ingredient": {"item": "p:c_dust"}, "result": "c:ingot"}},
                             {"id": "p:gear", "type": "shaped", "pattern": ["I", "C"], "key": {"I": "c:ingot", "C": "b:core"}, "result": "a:gear"}]},
                {"id": "chem", "title": "B infuses", "bridges": ["b", "a"], "items": [],
                 "recipes": [{"type": "custom", "json": {"type": "b:infusing", "chemicalInput": {"amount": 10, "tag": "b:carbon"},
                                                         "itemInput": {"ingredient": {"item": "a:sword"}}, "output": {"item": "b:core"}}}]}],
            "presets": {"hard": {"replace_inputs": [{"in": {"output": "a:gear"}, "from": "c:ingot", "to": "b:core"},
                                                    {"in": {"id": "p:c_dust"}, "from": "c:ore", "to": "a:sword"}]},
                        "easy": {"remove": [{"id": "p:c_smelt"}]}}}

    def test_merge_check_and_doc(self):
        rep = tune.check(self.DATA, self.IDX)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual((rep.items, rep.recipes, rep.integrations, rep.bridges), (1, 4, 2, ["a+b", "a+c"]))
        self.assertFalse(rep.warnings, rep.warnings)        # a chemical tag is not an item tag and is not checked
        md = tune.doc(self.DATA)
        self.assertIn("A pulverizes C", md); self.assertIn("c:ore -> p:c_dust x2 (a:pulverizer)", md); self.assertIn("| a + c |", md)

    def test_rules_on_own_recipes_are_baked(self):
        hard = tune.check(dict(self.DATA, difficulty="hard"), self.IDX)
        self.assertTrue(hard.ok, hard.errors); self.assertEqual(hard.replaced, 0)   # nothing left for KubeJS to modify
        eff = tune.bake(tune.effective(dict(self.DATA, difficulty="hard")), self.IDX, "p")
        self.assertEqual(eff["replace_inputs"], [])
        self.assertEqual(eff["recipes"][2]["key"], {"I": "b:core", "C": "b:core"})
        self.assertEqual(eff["recipes"][0]["json"]["ingredient"], {"item": "a:sword"})
        easy = tune.check(dict(self.DATA, difficulty="easy"), self.IDX)
        self.assertTrue(easy.ok, easy.errors); self.assertEqual((easy.recipes, easy.removed), (3, 0))
        self.assertNotIn('"p:c_smelt"', tune.server_script(tune.bake(tune.effective(dict(self.DATA, difficulty="easy")), self.IDX, "p")))

    def test_integration_errors(self):
        bad = json.loads(json.dumps(self.DATA)); bad["integrations"][0]["bridges"] = ["a"]
        self.assertTrue(any("at least two" in e for e in tune.check(bad, self.IDX).errors))
        bad = json.loads(json.dumps(self.DATA)); bad["integrations"][0]["bridges"] = ["a", "zzz"]
        self.assertTrue(any("zzz" in w for w in tune.check(bad, self.IDX).warnings))
        bad = json.loads(json.dumps(self.DATA)); bad["integrations"][1]["id"] = "dust"
        self.assertTrue(any("used twice" in e for e in tune.check(bad, self.IDX).errors))


class VisualDefaultsTests(unittest.TestCase):
    def test_options_and_shader_config(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "pack.json").write_text(json.dumps({"name": "P", "version": "1", "minecraft": "1.20.1", "loader": "forge"}))
            pack = load_pack(Path(d))
            pack.overrides.mkdir(); (pack.overrides / "options.txt").write_text("renderDistance:10\nresourcePacks:[\"vanilla\"]\n")
            files = [{"path": "resourcepacks/Faithful.zip"}, {"path": "shaderpacks/Comp.zip"}, {"path": "mods/x.jar"}]
            done = build.apply_visual_defaults(pack, files, log=lambda *a: None)
            self.assertEqual(done, {"resourcepacks": ["Faithful.zip"], "shaderpack": "Comp.zip"})
            opts = (pack.overrides / "options.txt").read_text()
            self.assertIn('resourcePacks:["vanilla", "mod_resources", "file/Faithful.zip"]', opts); self.assertIn("renderDistance:10", opts)
            self.assertEqual(opts.count("resourcePacks:"), 1)
            self.assertIn("shaderPack=Comp.zip\nenableShaders=true", (pack.overrides / "config" / "oculus.properties").read_text())


class TriageKubeTests(unittest.TestCase):
    def test_script_error_is_a_suspect(self):
        lines = ["[12:00:00] [main/INFO] [KubeJS]: Loaded script packloom.tune.js",
                 "[12:00:01] [main/ERROR] [KubeJS]: Error in 'server_scripts/packloom.tune.js': TypeError: Cannot read x",
                 "[12:00:09] [main/INFO]: Done (3.0s)! For help, type \"help\""]
        t = triage.analyze(lines)
        self.assertTrue(t.ok)
        self.assertEqual([(s.mod, s.kind) for s in t.suspects], [("kubejs-script", "script")])


class TuneVerifyTests(unittest.TestCase):
    def test_non_editable_type_warns_and_counts_compare(self):
        idx = json.loads(json.dumps(TuneTests.IDX))
        idx["recipe"]["q:quarry"] = {"type": "q:workbench_recipe", "result": "q:quarry", "inputs": ["#forge:ingots/iron"]}
        data = {"namespace": "p", "difficulty": "normal",
                "replace_inputs": [{"in": {"output": "q:quarry"}, "from": "#forge:ingots/iron", "to": "#forge:ingots/gold"}]}
        rep = tune.check(data, idx)
        self.assertTrue(rep.ok); self.assertEqual(rep.replaced, 1); self.assertIn("may not be able to edit", rep.warnings[0])
        with tempfile.TemporaryDirectory() as d:
            Path(d, "pack.json").write_text(json.dumps({"name": "P", "version": "1", "minecraft": "1.20.1", "loader": "forge"}))
            Path(d, "smoke-test.log").write_text("[1] [main/INFO] [KubeJS Server/]: Loaded script server_scripts:packloom.tune.js\n"
                                                 "[2] [main/INFO] [KubeJS Server/]: Added 0 recipes, removed 0 recipes, modified 0 recipes, with 0 failed recipes in 1 ms\n")
            v = tune.verify_logs(load_pack(Path(d)), rep)
            self.assertEqual(v["counts"]["modified"], 0)
            self.assertEqual(v["mismatch"], ["modified: tune.json expects 1, the server modified 0 (a rule on a recipe type KubeJS cannot edit?)"])


class PixelTests(unittest.TestCase):
    def test_ramp_is_hue_shifted_and_ordered(self):
        from packloom import pixel
        r = pixel.ramp("#ca6b1a", "metal")
        lum = [sum(pixel.hex_rgb(r[k])) for k in "oDMLHS"]
        self.assertEqual(lum, sorted(lum))                       # darker to lighter
        self.assertEqual(r["M"], "#ca6b1a")
        self.assertNotEqual(r["o"], "#000000")
        self.assertNotEqual(pixel.ramp("#ca6b1a", "energy")["D"], r["D"])

    def test_png_roundtrip_grid_and_adapt(self):
        from packloom import pixel
        spec = {"name": "t:ingot", "material": "metal", "color": "#ca6b1a", "extra": {"Y": "#ffe84a"},
                "grid": ["................"] * 6 + ["....MMMMMMMM....", "....MYMMMMMM....", "....DDDDDDDD...."] + ["................"] * 7}
        px = pixel.build_icon(spec)
        self.assertEqual(px[5][4][3], 255)                       # auto outline above the body
        self.assertEqual(px[0][0][3], 0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.png"
            pixel.write_png(path, px)
            back = pixel.read_png(path.read_bytes())
        self.assertEqual(back, px)
        rows, legend = pixel.to_grid(px)
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[9][4], "o")                        # the outline is the darkest colour
        self.assertEqual(legend["o"], pixel.ramp("#ca6b1a", "metal")["o"])
        grid, extra = pixel.adapt(px)
        self.assertEqual(grid[6][4], "M")
        self.assertIn(grid[8][4], "oD")
        self.assertEqual(extra, {})
        with self.assertRaises(ValueError):
            pixel.parse_grid(["..."] * 16)

    def test_sheet_and_handle(self):
        from packloom import pixel
        g = pixel.parse_grid(["................"] * 16)
        pixel.handle(g, 3, 11, 9)
        self.assertEqual(g[3][9], "w"); self.assertEqual(g[3][10], "h"); self.assertEqual(g[11][1], "w")
        sheet = pixel.sheet([pixel.render(g, {"w": "#493615", "h": "#684e1e", "a": "#281e0b"})] * 2, scale=2, cols=2)
        self.assertEqual((len(sheet[0]), len(sheet)), (2 * 17 * 2, 17 * 2))

    def test_borrowed_texture_in_startup_script(self):
        from packloom import tune
        js = tune.startup_script([{"id": "t:dust", "icon": {"texture": "divinerpg:item/realmite_dust"}}])
        self.assertIn('.texture("divinerpg:item/realmite_dust")', js)


class CatalogPageTests(unittest.TestCase):
    def test_page_embeds_families_for_the_pack(self):
        from packloom import cli
        from packloom.manifest import Pack
        with tempfile.TemporaryDirectory() as d:
            pack = Pack(dir=Path(d), name="T", version="1", minecraft="1.20.1", loader="forge")
            info = cli.cmd_catalog_page(pack, Path(d) / "catalog.html")
            html = (Path(d) / "catalog.html").read_text()
        self.assertEqual(info["game"], "1.20.1/forge")
        self.assertGreater(info["families"], 70)
        self.assertIn('"id": "thermal"', html)
        self.assertNotIn("/*DATA*/", html)
        self.assertIn("picks/current", html)


class PicksTests(unittest.TestCase):
    """`design --picks` takes the document the catalog page wrote and runs the same proposal."""
    DOC = {"game": "1.20.1/forge", "want": ["tech"], "avoid": [], "include": ["divinerpg"], "exclude": [], "grind": "low",
           "difficulty": "easy", "families": ["thermal", "divinerpg"], "command": "design --want tech --include divinerpg --grind low"}

    def _run(self, argv):
        import io, contextlib
        from packloom import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(argv)
        return out.getvalue()

    def test_picks_fill_the_flags_and_the_game(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "picks.json"; f.write_text(json.dumps(self.DOC))
            prop = json.loads(self._run(["design", "--picks", str(f), "--json"]))
        self.assertEqual(prop["grind"], "low"); self.assertEqual(prop["difficulty"], "easy")
        ids = [p["id"] for p in prop["families"]]
        self.assertIn("divinerpg", ids); self.assertIn("thermal", ids)

    def test_flags_win_over_the_page_and_envelope_is_unwrapped(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "picks.json"; f.write_text(json.dumps({"data": self.DOC}))   # ArtifactData get envelope
            prop = json.loads(self._run(["design", "--picks", str(f), "--grind", "high", "--json"]))
        self.assertEqual(prop["grind"], "high")

    def test_write_keeps_the_pick_next_to_mods_txt(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "picks.json"; f.write_text(json.dumps(self.DOC))
            self._run(["init", "--dir", d, "--name", "T", "--minecraft", "1.20.1", "--loader", "forge"])
            out = self._run(["--pack", d, "design", "--picks", str(f), "--write", "--force"])
            self.assertIn("different set", out)      # the sample doc lists two families; design picks the defaults too
            saved = json.loads((Path(d) / "picks.json").read_text())
            self.assertEqual(saved["families"], ["thermal", "divinerpg"])
            self.assertIn("divinerpg", (Path(d) / "mods.txt").read_text())

    def test_a_file_that_is_not_a_pick_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.json"; f.write_text("{}")
            with self.assertRaises(SystemExit):
                self._run(["design", "--picks", str(f)])


class GrindAndBalanceTests(unittest.TestCase):
    def test_grind_levels_and_ladder(self):
        from packloom import catalog
        cat = catalog.load()
        low = catalog.design(cat, "1.20.1", "forge", ["tech", "rpg"], grind="low", include=["draconic"])
        self.assertEqual(low.difficulty, "easy")
        self.assertIn("divinerpg", [i for i, _ in low.skipped])
        self.assertIn("draconic", low.ladder()["endgame"])
        self.assertTrue(any("peak at endgame" in b for b in low.balance))
        self.assertTrue(any("kept at low grind" in w for p in low.picks if p.family["id"] == "draconic" for w in p.warnings))
        high = catalog.design(cat, "1.20.1", "forge", ["tech", "rpg"], grind="high")
        self.assertEqual(high.difficulty, "hard")
        self.assertIn("divinerpg", [p.family["id"] for p in high.picks])
        self.assertIn("balance", high.as_dict())
        self.assertTrue(all(f.get("power") in catalog.STAGES + ("any",) for f in cat["families"]))
        self.assertTrue(cat["missing"][0]["instead"])
