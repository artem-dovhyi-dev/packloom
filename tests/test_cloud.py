"""packloom.cloud against a fake Vultr: the API state machine, ssh and rcon are all in memory."""
import base64
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from packloom import cloud, cloud_agent  # noqa: E402
from packloom.manifest import Pack  # noqa: E402


class FakeVultr:
    """Enough of api.vultr.com/v2 for setup/up/down/status/teardown. Records every call."""

    def __init__(self):
        self.calls = []
        self.instances, self.blocks, self.snapshots, self.ssh_keys, self.firewalls, self.rules, self.rips = {}, {}, {}, {}, {}, {}, {}
        self.n = 0
        self.stopped = set()   # instance ids whose server got `stop`; the fake agent deletes them on the next poll

    def _id(self, prefix):
        self.n += 1
        return f"{prefix}-{self.n}"

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        p = path.split("?")[0]
        if p == "/regions":
            return {"regions": [{"id": "sgp", "options": ["block_storage_high_perf", "block_storage_storage_opt"]},
                                {"id": "waw", "options": ["block_storage_storage_opt"]}], "meta": {}}
        if p == "/plans":
            return {"plans": [{"id": "vc2-4c-8gb", "ram": 8192, "monthly_cost": 40, "locations": ["sgp", "waw"]}], "meta": {}}
        if p == "/os":
            return {"os": [{"id": 2284, "name": cloud.UBUNTU_LTS}], "meta": {}}
        if p == "/ssh-keys":
            if method == "POST":
                k = {"id": self._id("key"), **body}; self.ssh_keys[k["id"]] = k; return {"ssh_key": k}
            return {"ssh_keys": list(self.ssh_keys.values()), "meta": {}}
        if p == "/firewalls":
            if method == "POST":
                g = {"id": self._id("fw"), **body}; self.firewalls[g["id"]] = g; return {"firewall_group": g}
            return {"firewall_groups": list(self.firewalls.values()), "meta": {}}
        m = re.match(r"/firewalls/(.+)/rules", p)
        if m:
            self.rules.setdefault(m.group(1), []).append(body); return {}
        if p == "/blocks" and method == "POST":
            b = {"id": self._id("blk"), "status": "active", "attached_to_instance": "", **body}; self.blocks[b["id"]] = b; return {"block": b}
        m = re.match(r"/blocks/([^/]+)(/attach|/detach)?$", p)
        if m:
            b = self.blocks[m.group(1)]
            if m.group(2) == "/attach":
                b["attached_to_instance"] = body["instance_id"]; return {}
            if m.group(2) == "/detach":
                b["attached_to_instance"] = ""; return {}
            if method == "DELETE":
                del self.blocks[b["id"]]; return {}
            return {"block": b}
        if p == "/reserved-ips" and method == "POST":
            r = {"id": self._id("rip"), "subnet": "203.0.113.7", **body}; self.rips[r["id"]] = r; return {"reserved_ip": r}
        m = re.match(r"/reserved-ips/(.+)", p)
        if m and method == "DELETE":
            del self.rips[m.group(1)]; return {}
        if p == "/instances":
            if method == "POST":
                i = {"id": self._id("inst"), "status": "active", "power_status": "running", "server_status": "ok",
                     "main_ip": body.get("reserved_ipv4") or "198.51.100.9", "date_created": "2026-11-05T10:00:00+00:00", **body}
                self.instances[i["id"]] = i; return {"instance": i}
            return {"instances": list(self.instances.values()), "meta": {}}
        m = re.match(r"/instances/(.+)", p)
        if m:
            iid = m.group(1)
            if method == "DELETE":
                self.instances.pop(iid, None); return {}
            if iid in self.stopped:          # the agent on the server finalized and deleted it
                self.instances.pop(iid, None)
            if iid not in self.instances:
                raise cloud.VultrError(f"GET {p}: HTTP 404")
            return {"instance": self.instances[iid]}
        if p == "/snapshots" and method == "POST":
            s = {"id": self._id("snap"), "status": "complete", **body}; self.snapshots[s["id"]] = s; return {"snapshot": s}
        m = re.match(r"/snapshots/(.+)", p)
        if m:
            if method == "DELETE":
                self.snapshots.pop(m.group(1), None); return {}
            return {"snapshot": self.snapshots[m.group(1)]}
        raise AssertionError(f"unexpected {method} {path}")


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.pack = Pack(dir=d, name="TechPack", version="1.1.0", minecraft="1.20.1", loader="forge", memory_mb=6144)
        (d / "dist").mkdir()
        self.bundle = d / "dist" / "TechPack-1.1.0-server.zip"
        self.bundle.write_bytes(b"zip" * 1000)
        self.api = FakeVultr()
        self.shell_log = []
        self.rcon_log = []
        self.players = 0

        def shell(ip, script=None, upload=None, remote="/root/"):
            self.shell_log.append((ip, script, upload))
            return "PROVISIONED\n" if script else ""

        def rcon_fn(host, port, password, command):
            self.rcon_log.append((host, command))
            if command == "stop":
                for i in self.api.instances.values():
                    if i["label"].endswith("-game"):
                        self.api.stopped.add(i["id"])
            return f"There are {self.players} of a max of 8 players online:"

        self.state = cloud.CloudState()
        self.c = cloud.Cloud(self.pack, cloud.Vultr("k", transport=self.api), {"VULTR_API_KEY": "k", "RCON_PASSWORD": "pw"},
                             self.state, log=lambda *a: None, sleep=lambda s: None, shell=shell, rcon_fn=rcon_fn,
                             port_open=lambda ip, port: True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_setup_builds_snapshot_and_deletes_base(self):
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        ids = self.state.ids
        self.assertEqual(set(ids), {"sshkey", "firewall", "block", "reserved_ip", "reserved_ip_id", "snapshot", "snapshot_bundle"})
        self.assertEqual(ids["reserved_ip"], "203.0.113.7")
        self.assertEqual(self.api.instances, {}, "base server must be deleted after the snapshot")
        self.assertEqual(self.api.blocks[ids["block"]]["attached_to_instance"], "", "volume detached before snapshot")
        self.assertEqual(self.api.blocks[ids["block"]]["block_type"], "high_perf")
        ports = {(r["protocol"], r["port"]) for r in self.api.rules[ids["firewall"]]}
        self.assertEqual(ports, {("tcp", "22"), ("tcp", "25565"), ("udp", "24454")})
        uploads = [u.name for _, s, u in self.shell_log if u]
        self.assertEqual(uploads, ["TechPack-1.1.0-server.zip", "cloud_agent.py"])
        script = next(s for _, s, _ in self.shell_log if s)
        self.assertIn("rcon.password=pw", script)
        self.assertIn("ln -s /srv/techpack/world /opt/techpack/world", script)
        self.assertIn("systemctl enable techpack-boot.service", script)
        self.assertEqual(self.state.extra["plan_ram_mb"], 8192)
        self.assertTrue((self.pack.dir / "cloud" / "cloud.json").exists())
        self.assertEqual((self.pack.dir / "cloud" / ".gitignore").read_text(), ".env\nknown_hosts\n")

    def test_setup_is_idempotent_until_rebuild(self):
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        first = dict(self.state.ids)
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        self.assertEqual(self.state.ids, first)
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test", rebuild=True)
        self.assertNotEqual(self.state.ids["snapshot"], first["snapshot"])
        self.assertNotIn(first["snapshot"], self.api.snapshots, "old snapshot deleted after rebuild")
        self.assertEqual(self.state.ids["block"], first["block"], "the world volume survives a rebuild")

    def test_hdd_region_bumps_volume_to_40(self):
        self.state.region = "waw"
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        b = self.api.blocks[self.state.ids["block"]]
        self.assertEqual((b["block_type"], b["size_gb"]), ("storage_opt", 40))

    def test_up_down_cycle(self):
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        inst = self.c.up()
        self.assertEqual(inst["snapshot_id"], self.state.ids["snapshot"])
        self.assertEqual(inst["reserved_ipv4"], "203.0.113.7")
        self.assertEqual(self.api.blocks[self.state.ids["block"]]["attached_to_instance"], inst["id"])
        env = base64.b64decode(inst["user_data"]).decode()
        self.assertIn("VULTR_API_KEY=k\n", env)
        self.assertIn("RCON_PASSWORD=pw\n", env)
        self.assertIn(f"BLOCK_ID={self.state.ids['block']}\n", env)
        self.assertIn(("203.0.113.7", "list"), self.rcon_log)
        self.assertEqual(self.c.up()["id"], inst["id"], "second up is a no-op")

        self.players = 2
        s = self.c.status()
        self.assertEqual((s["players"], s["running"]["ip"], s["cost_usd"]), (2, "203.0.113.7", s["cost_usd"]))
        self.assertGreater(s["cost_usd"], 0)

        self.assertTrue(self.c.down())
        self.assertIn(("203.0.113.7", "stop"), self.rcon_log)
        self.assertEqual(self.api.instances, {})
        self.assertFalse(self.c.down(), "nothing to stop")
        self.assertIsNone(self.c.status()["running"])

    def test_down_force_when_rcon_dead(self):
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        self.c.up()

        def dead(*a):
            raise OSError("refused")
        self.c.rcon_fn = dead
        self.assertTrue(self.c.down())
        self.assertEqual(self.api.instances, {})
        self.assertIn(("DELETE", f"/instances/inst-{self.api.n}", None), self.api.calls)

    def test_up_refuses_while_volume_attached(self):
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        self.api.blocks[self.state.ids["block"]]["attached_to_instance"] = "ghost"
        with self.assertRaises(RuntimeError):
            self.c.up()

    def test_teardown_removes_everything(self):
        self.c.setup(self.bundle, "47.4.28", "ssh-ed25519 AAAA test")
        self.c.up()
        self.c.teardown()
        self.assertEqual((self.api.instances, self.api.blocks, self.api.snapshots, self.api.rips), ({}, {}, {}, {}))
        self.assertEqual(set(self.state.ids), {"sshkey", "firewall"})


class PureTests(unittest.TestCase):
    def test_players_online(self):
        self.assertEqual(cloud_agent.players_online("There are 3 of a max of 8 players online: a, b, c"), 3)
        self.assertEqual(cloud_agent.players_online("There are 0 of a max of 8 players online:"), 0)
        self.assertIsNone(cloud_agent.players_online("Unknown command"))

    def test_state_roundtrip_keeps_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cloud.json"
            p.write_text(json.dumps({"region": "waw", "ids": {"block": "b1"}, "note": "kept"}))
            st = cloud.CloudState.load(p)
            self.assertEqual((st.region, st.plan, st.ids), ("waw", "vc2-4c-8gb", {"block": "b1"}))
            st.save(p)
            self.assertEqual(json.loads(p.read_text())["note"], "kept")

    def test_agent_is_standalone(self):
        src = Path(cloud_agent.__file__).read_text()
        self.assertNotIn("from packloom", src)
        self.assertNotIn("from .", src)

    def test_label_is_dns_safe(self):
        self.assertEqual(cloud.label_for(Pack(dir=Path("."), name="Tech Pack!", version="1", minecraft="1.20.1", loader="forge")), "tech-pack-")

    def test_idle_policy(self):
        stop = cloud_agent.should_stop
        self.assertFalse(stop(players=2, idle_minutes=0, uptime_minutes=120, idle_limit=30, grace=15), "people are playing")
        self.assertFalse(stop(players=0, idle_minutes=5, uptime_minutes=5, idle_limit=30, grace=15), "just booted, friends still joining")
        self.assertFalse(stop(players=0, idle_minutes=10, uptime_minutes=100, idle_limit=30, grace=15), "idle, but not for long enough")
        self.assertTrue(stop(players=0, idle_minutes=31, uptime_minutes=100, idle_limit=30, grace=15), "idle past the limit")
        self.assertTrue(stop(players=0, idle_minutes=20, uptime_minutes=20, idle_limit=30, grace=15),
                        "nobody ever joined after `up`: the grace period is the limit, not idle_limit")


if __name__ == "__main__":
    unittest.main()
