"""Stdlib unittest; run with: python3 -m unittest discover -s tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from packloom import keybinds, triage  # noqa: E402
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
        s = keybinds.summary(bs)
        self.assertEqual(s["unbound"], 1)
        self.assertEqual(list(s["conflicts"]), ["key.keyboard.b"])   # SHIFT+B is a different chord

    def test_render_is_self_contained(self):
        html = keybinds.render_html(keybinds.parse_options("key_key.inventory:key.keyboard.e\n"), "T")
        self.assertIn("<title>T</title>", html)
        self.assertIn('"key.keyboard.e"', html)
        self.assertNotIn("__DATA__", html)


if __name__ == "__main__":
    unittest.main()
