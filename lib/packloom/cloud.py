"""An on-demand server in the cloud: pay only while people play.

Vultr bills by the hour and keeps billing a powered-off server, so the only cheap server is one that does not
exist between sessions. Three pieces make that workable:

  * a block storage volume that holds the world (survives the server, ~1 $/month),
  * a snapshot of a fully installed server (Java, loader, mods) so `up` is a deploy, not an install,
  * an agent on the server (cloud_agent.py) that watches the player count and destroys the server itself when
    nobody plays, so forgetting `down` costs nothing.

A reserved IP keeps the address the same across servers, so friends add it once.

State lives in <pack>/cloud/cloud.json (ids of the things above) and secrets in <pack>/cloud/.env
(VULTR_API_KEY, RCON_PASSWORD). Run as `python3 -m packloom.cloud --pack <dir> <init|setup|up|down|status|teardown>`.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import USER_AGENT, loaders
from .cloud_agent import players_online, rcon
from .manifest import Pack, find_pack_dir, load_pack

API = "https://api.vultr.com/v2"
UBUNTU_LTS = "Ubuntu 24.04 LTS x64"
SERVER_ROOT = "/opt/techpack"          # where the bundle lives on the server
AGENT_ROOT = "/opt/techpack-agent"
VOLUME_LABEL = "techpack"
MOUNT = "/srv/techpack"
PERSISTENT = ("world", "ops.json", "whitelist.json", "banned-players.json", "banned-ips.json", "usercache.json")
METADATA = "http://169.254.169.254"
RCON_PORT = 25575


# --- Vultr API client --------------------------------------------------------------------------------------

class VultrError(RuntimeError):
    pass


class Vultr:
    """Thin client over Vultr API v2. `transport` is swapped in tests."""

    def __init__(self, api_key: str, transport: Optional[Callable] = None):
        self.api_key = api_key
        self._transport = transport or self._http

    def _http(self, method: str, path: str, body: Optional[dict]) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": USER_AGENT,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raise VultrError(f"{method} {path}: HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None

    def call(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        return self._transport(method, path, body)

    def list_all(self, path: str, key: str) -> list:
        out, cursor = [], None
        while True:
            page = self.call("GET", path + ("&" if "?" in path else "?") + "per_page=500" + (f"&cursor={cursor}" if cursor else ""))
            out += page.get(key, [])
            cursor = page.get("meta", {}).get("links", {}).get("next") or None
            if not cursor:
                return out

    # account-level things, created once
    def ssh_key_id(self, name: str, public_key: str) -> str:
        for k in self.list_all("/ssh-keys", "ssh_keys"):
            if k["ssh_key"].split()[:2] == public_key.split()[:2]:
                return k["id"]
        return self.call("POST", "/ssh-keys", {"name": name, "ssh_key": public_key})["ssh_key"]["id"]

    def firewall_group(self, description: str, rules: list[tuple[str, str, str]]) -> str:
        """rules: (protocol, port, note). Opens them to the world; the rest stays closed (rcon among it)."""
        for g in self.list_all("/firewalls", "firewall_groups"):
            if g["description"] == description:
                return g["id"]
        gid = self.call("POST", "/firewalls", {"description": description})["firewall_group"]["id"]
        for proto, port, note in rules:
            self.call("POST", f"/firewalls/{gid}/rules", {"ip_type": "v4", "protocol": proto, "port": port,
                                                          "subnet": "0.0.0.0", "subnet_size": 0, "notes": note})
        return gid

    def create_block(self, region: str, size_gb: int, label: str, block_type: str) -> dict:
        return self.call("POST", "/blocks", {"region": region, "size_gb": size_gb, "label": label, "block_type": block_type})["block"]

    def block(self, block_id: str) -> dict:
        return self.call("GET", f"/blocks/{block_id}")["block"]

    def attach_block(self, block_id: str, instance_id: str):
        self.call("POST", f"/blocks/{block_id}/attach", {"instance_id": instance_id, "live": True})

    def detach_block(self, block_id: str):
        self.call("POST", f"/blocks/{block_id}/detach", {"live": True})

    def create_reserved_ip(self, region: str, label: str) -> dict:
        return self.call("POST", "/reserved-ips", {"region": region, "ip_type": "v4", "label": label})["reserved_ip"]

    def os_id(self, name: str) -> int:
        for o in self.list_all("/os", "os"):
            if o["name"] == name:
                return o["id"]
        raise VultrError(f"OS image {name!r} not offered by Vultr any more; pick another in cloud.json")

    def region(self, region_id: str) -> dict:
        for r in self.list_all("/regions", "regions"):
            if r["id"] == region_id:
                return r
        raise VultrError(f"unknown region {region_id!r}")

    def plan(self, plan_id: str) -> dict:
        for p in self.list_all("/plans", "plans"):
            if p["id"] == plan_id:
                return p
        raise VultrError(f"unknown plan {plan_id!r}")

    # instances
    def create_instance(self, **body) -> dict:
        return self.call("POST", "/instances", body)["instance"]

    def instance(self, instance_id: str) -> Optional[dict]:
        try:
            return self.call("GET", f"/instances/{instance_id}")["instance"]
        except VultrError as e:
            if "HTTP 404" in str(e):
                return None
            raise

    def instances(self, label_prefix: str) -> list[dict]:
        return [i for i in self.list_all("/instances", "instances") if i.get("label", "").startswith(label_prefix)]

    def delete_instance(self, instance_id: str):
        self.call("DELETE", f"/instances/{instance_id}")

    def create_snapshot(self, instance_id: str, description: str) -> dict:
        return self.call("POST", "/snapshots", {"instance_id": instance_id, "description": description})["snapshot"]

    def snapshot(self, snapshot_id: str) -> dict:
        return self.call("GET", f"/snapshots/{snapshot_id}")["snapshot"]

    def delete_snapshot(self, snapshot_id: str):
        self.call("DELETE", f"/snapshots/{snapshot_id}")

    def delete_block(self, block_id: str):
        self.call("DELETE", f"/blocks/{block_id}")

    def delete_reserved_ip(self, rip_id: str):
        self.call("DELETE", f"/reserved-ips/{rip_id}")


# --- state ---------------------------------------------------------------------------------------------------

@dataclass
class CloudState:
    provider: str = "vultr"
    region: str = "sgp"
    plan: str = "vc2-4c-8gb"
    os: str = UBUNTU_LTS
    volume_gb: int = 10
    idle_minutes: int = 30          # agent: stop after this long with nobody online
    grace_minutes: int = 15         # agent: never stop in the first minutes after boot
    ids: dict = field(default_factory=dict)   # sshkey, firewall, block, reserved_ip, reserved_ip_id, snapshot, snapshot_bundle
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "CloudState":
        d = json.loads(path.read_text()) if path.exists() else {}
        known = {k: d.pop(k) for k in list(d) if k in cls.__dataclass_fields__}
        return cls(**known, extra=d)

    def save(self, path: Path):
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "extra"} | self.extra
        path.write_text(json.dumps(d, indent=2) + "\n")


def cloud_dir(pack: Pack) -> Path:
    d = pack.dir / "cloud"
    d.mkdir(exist_ok=True)
    gi = d / ".gitignore"
    if not gi.exists():
        gi.write_text(".env\nknown_hosts\n")
    return d


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env


def label_for(pack: Pack) -> str:
    return re.sub(r"[^a-z0-9-]", "-", pack.name.lower())


# --- what runs on the server ---------------------------------------------------------------------------------

SYSTEMD_SERVER = """[Unit]
Description={label} Minecraft server
After=network-online.target

[Service]
Type=simple
WorkingDirectory={root}
Environment=MEM={mem}G
ExecStart={root}/start.sh
ExecStop=/usr/bin/python3 {agent}/cloud_agent.py rcon stop
TimeoutStopSec=180
Restart=no
"""

SYSTEMD_AGENT = """[Unit]
Description={label} idle watchdog: destroys this server when nobody plays
After={label}.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 {agent}/cloud_agent.py run
Restart=on-failure
RestartSec=30
"""

SYSTEMD_BOOT = """[Unit]
Description={label} boot: read user-data, mount the world volume, start the server
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {agent}/cloud_agent.py boot
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""


def provision_script(pack: Pack, bundle_name: str, loader_version: str, label: str, mem_gb: int) -> str:
    """Runs once over ssh on the throwaway base server, before the snapshot. Everything idempotent."""
    installer = loaders.server_installer_url(pack.loader, pack.minecraft, loader_version)
    units = {
        f"{label}.service": SYSTEMD_SERVER.format(label=label, root=SERVER_ROOT, mem=mem_gb, agent=AGENT_ROOT),
        f"{label}-agent.service": SYSTEMD_AGENT.format(label=label, agent=AGENT_ROOT),
        f"{label}-boot.service": SYSTEMD_BOOT.format(label=label, agent=AGENT_ROOT),
    }
    lines = [
        "set -e",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update -qq",
        f"apt-get install -y -qq openjdk-{pack.java_major}-jre-headless unzip >/dev/null",
        f"rm -rf {SERVER_ROOT} && mkdir -p {SERVER_ROOT} {AGENT_ROOT} {MOUNT}",
        f"unzip -q -o /root/{bundle_name} -d /root/bundle-tmp && mv /root/bundle-tmp/*/* {SERVER_ROOT}/ && rm -rf /root/bundle-tmp /root/{bundle_name}",
        f"mv /root/cloud_agent.py {AGENT_ROOT}/cloud_agent.py",
        f"cd {SERVER_ROOT} && curl -fsSL -o installer.jar {shlex.quote(installer)} && java -jar installer.jar --installServer >install.log 2>&1 && rm -f installer.jar",
        f"cd {SERVER_ROOT} && echo eula=true > eula.txt",
        # the world and the player lists live on the volume; the snapshot only holds symlinks to them
        "DEV=$(lsblk -dn -o NAME,TYPE | awk '$2==\"disk\" && $1!=\"vda\" {print $1; exit}')",
        'test -n "$DEV" || { echo "no data disk attached"; exit 1; }',
        f'blkid -L {VOLUME_LABEL} >/dev/null 2>&1 || mkfs.ext4 -q -L {VOLUME_LABEL} "/dev/$DEV"',
        f"mount -L {VOLUME_LABEL} {MOUNT}",
        f"mkdir -p {MOUNT}/world {MOUNT}/logs",
    ]
    for name in PERSISTENT:
        if name.endswith(".json"):
            lines.append(f"test -e {MOUNT}/{name} || echo '[]' > {MOUNT}/{name}")
        lines.append(f"rm -rf {SERVER_ROOT}/{name} && ln -s {MOUNT}/{name} {SERVER_ROOT}/{name}")
    lines += [
        f"umount {MOUNT}",
        # rcon is how the agent and `down` talk to the server; the firewall keeps the port off the internet
        f"cd {SERVER_ROOT} && sed -i -e '/^enable-rcon=/d' -e '/^rcon.port=/d' -e '/^rcon.password=/d' -e '/^broadcast-rcon-to-ops=/d' server.properties",
        f"cd {SERVER_ROOT} && printf 'enable-rcon=true\\nrcon.port={RCON_PORT}\\nrcon.password=__RCON__\\nbroadcast-rcon-to-ops=false\\n' >> server.properties",
        f"chmod 600 {SERVER_ROOT}/server.properties",
    ]
    for name, text in units.items():
        lines.append(f"cat > /etc/systemd/system/{name} <<'EOF'\n{text}EOF")
    lines += ["systemctl daemon-reload", f"systemctl enable {label}-boot.service >/dev/null 2>&1",
              "apt-get clean", "sync", "echo PROVISIONED"]
    return "\n".join(lines) + "\n"


def user_data(label: str, api_key: str, rcon_password: str, state: CloudState) -> str:
    """Plain KEY=VALUE text the agent reads from the metadata service at boot. Base64 for the API."""
    text = (f"LABEL={label}\nVULTR_API_KEY={api_key}\nRCON_PASSWORD={rcon_password}\nRCON_PORT={RCON_PORT}\n"
            f"IDLE_MINUTES={state.idle_minutes}\nGRACE_MINUTES={state.grace_minutes}\nBLOCK_ID={state.ids.get('block', '')}\n"
            f"SERVER_ROOT={SERVER_ROOT}\nMOUNT={MOUNT}\nVOLUME_LABEL={VOLUME_LABEL}\n")
    return base64.b64encode(text.encode()).decode()


# --- orchestration -------------------------------------------------------------------------------------------

class Cloud:
    def __init__(self, pack: Pack, api: Vultr, env: dict, state: CloudState, log=print, sleep=time.sleep,
                 shell: Optional[Callable] = None, rcon_fn: Callable = rcon, port_open: Optional[Callable] = None):
        self.pack, self.api, self.env, self.state = pack, api, env, state
        self.log, self.sleep, self.rcon_fn = log, sleep, rcon_fn
        self.shell = shell or self._ssh
        self.port_open = port_open or self._port_open
        self.label = label_for(pack)
        self.dir = cloud_dir(pack)

    # -- helpers
    def save(self):
        self.state.save(self.dir / "cloud.json")

    def _ssh_opts(self) -> list[str]:
        return ["-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={self.dir / 'known_hosts'}",
                "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR"]

    def _ssh(self, ip: str, script: Optional[str] = None, upload: Optional[Path] = None, remote: str = "/root/") -> str:
        """Upload a file or run a script as root. Returns stdout. One ssh/scp call per step keeps it readable."""
        if upload is not None:
            r = subprocess.run(["scp", *self._ssh_opts(), str(upload), f"root@{ip}:{remote}"], capture_output=True, text=True)
        else:
            r = subprocess.run(["ssh", *self._ssh_opts(), f"root@{ip}", "sh", "-s"], input=script, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ssh {ip} failed ({r.returncode}): {r.stderr.strip()[-800:]}\n{r.stdout[-800:]}")
        return r.stdout

    def wait(self, what: str, probe: Callable[[], bool], timeout: int, every: int = 10):
        t0 = time.monotonic()
        while True:
            if probe():
                return
            if time.monotonic() - t0 > timeout:
                raise TimeoutError(f"gave up waiting for {what} after {timeout} s")
            self.sleep(every)

    def _instance_ready(self, instance_id: str) -> Optional[dict]:
        i = self.api.instance(instance_id)
        if i and i.get("status") == "active" and i.get("power_status") == "running" and i.get("main_ip") not in (None, "", "0.0.0.0"):
            return i
        return None

    def _wait_instance(self, instance_id: str, timeout: int = 600) -> dict:
        self.wait("the server to boot", lambda: self._instance_ready(instance_id) is not None, timeout)
        return self._instance_ready(instance_id)

    @staticmethod
    def _port_open(ip: str, port: int) -> bool:
        try:
            with socket.create_connection((ip, port), timeout=5):
                return True
        except OSError:
            return False

    def _wait_ssh(self, ip: str, timeout: int = 300):
        self.wait("ssh", lambda: self.port_open(ip, 22), timeout, every=5)

    def _rcon(self, ip: str, command: str) -> str:
        return self.rcon_fn(ip, RCON_PORT, self.env["RCON_PASSWORD"], command)

    def mem_gb(self) -> int:
        ram_mb = self.state.extra.get("plan_ram_mb") or 8192
        return max(4, ram_mb // 1024 - 2)

    def running(self) -> list[dict]:
        return [i for i in self.api.instances(self.label) if not i.get("label", "").endswith("-base")]

    # -- commands
    def setup(self, bundle_zip: Path, loader_version: str, public_key: str, rebuild: bool = False):
        st, ids = self.state, self.state.ids
        region = self.api.region(st.region)
        plan = self.api.plan(st.plan)
        if st.region not in plan.get("locations", []):
            raise VultrError(f"plan {st.plan} is not sold in {st.region}")
        st.extra["plan_ram_mb"] = plan["ram"]
        st.extra["plan_monthly_usd"] = plan["monthly_cost"]
        opts = region.get("options", [])
        block_type = "high_perf" if "block_storage_high_perf" in opts else "storage_opt"
        size = st.volume_gb if block_type == "high_perf" else max(st.volume_gb, 40)
        if block_type == "storage_opt" and st.volume_gb < 40:
            self.log(f"{st.region} has only HDD block storage (40 GB minimum); using 40 GB")

        ids.setdefault("sshkey", self.api.ssh_key_id(f"{self.label}-cloud", public_key))
        ids.setdefault("firewall", self.api.firewall_group(f"{self.label}-cloud", [
            ("tcp", "22", "ssh for setup and debugging"), ("tcp", "25565", "minecraft"), ("udp", "24454", "simple voice chat")]))
        if "block" not in ids:
            b = self.api.create_block(st.region, size, f"{self.label}-world", block_type)
            ids["block"] = b["id"]
            self.log(f"volume {b['id']} ({size} GB {block_type}) created")
        if "reserved_ip" not in ids:
            r = self.api.create_reserved_ip(st.region, f"{self.label}-ip")
            ids["reserved_ip"], ids["reserved_ip_id"] = r["subnet"], r["id"]
            self.log(f"reserved IP {r['subnet']}: this is the address friends will use")
        self.save()
        self.wait("the volume", lambda: self.api.block(ids["block"]).get("status") == "active", 300)

        if "snapshot" in ids and not rebuild:
            self.log(f"snapshot {ids['snapshot']} exists; pass --rebuild to make a new one from the current bundle")
            return
        if self.running():
            raise RuntimeError("a game server is up; run `down` before rebuilding the snapshot")

        self.log(f"creating a base server in {st.region} from {st.os} (billed only during setup, ~20 min)")
        base = self.api.create_instance(region=st.region, plan=st.plan, os_id=self.api.os_id(st.os), label=f"{self.label}-base",
                                        hostname=f"{self.label}-base", sshkey_id=[ids["sshkey"]], firewall_group_id=ids["firewall"],
                                        backups="disabled", enable_ipv6=False, tags=[self.label])
        base_id = base["id"]
        try:
            inst = self._wait_instance(base_id)
            ip = inst["main_ip"]
            self.log(f"base server {ip} is up; attaching the volume and waiting for ssh")
            self.api.attach_block(ids["block"], base_id)
            self._wait_ssh(ip)
            self.sleep(20)   # cloud-init finishes writing the ssh key a little after sshd answers
            self.log(f"uploading {bundle_zip.name} ({bundle_zip.stat().st_size >> 20} MB) and the agent")
            self.shell(ip, upload=bundle_zip)
            self.shell(ip, upload=Path(__file__).with_name("cloud_agent.py"))
            self.log("installing Java, the loader and the systemd units (a few minutes)")
            script = provision_script(self.pack, bundle_zip.name, loader_version, self.label, self.mem_gb())
            out = self.shell(ip, script=script.replace("__RCON__", self.env["RCON_PASSWORD"]))
            if "PROVISIONED" not in out:
                raise RuntimeError("provisioning did not finish:\n" + out[-1500:])
            self.api.detach_block(ids["block"])
            self.sleep(10)
            self.log("taking the snapshot (Vultr needs 5-15 minutes for this)")
            snap = self.api.create_snapshot(base_id, f"{self.label} {self.pack.version} {bundle_zip.name}")
            old = ids.get("snapshot")
            ids["snapshot"], ids["snapshot_bundle"] = snap["id"], bundle_zip.name
            self.save()
            self.wait("the snapshot", lambda: self.api.snapshot(snap["id"]).get("status") == "complete", 2400, every=30)
            if old and old != snap["id"]:
                self.api.delete_snapshot(old)
        finally:
            self.log("deleting the base server")
            self.api.delete_instance(base_id)
        self.log(f"setup done. `up` deploys {ids['snapshot']} on {ids['reserved_ip']}; `down` or {st.idle_minutes} idle minutes remove it")

    def up(self) -> dict:
        st, ids = self.state, self.state.ids
        if "snapshot" not in ids:
            raise RuntimeError("run `setup` first")
        live = self.running()
        if live:
            self.log(f"already up: {live[0]['main_ip']}")
            return live[0]
        if self.api.block(ids["block"]).get("attached_to_instance"):
            raise RuntimeError("the world volume is still attached to a server that is going away; try again in a minute")
        self.log(f"deploying {st.plan} in {st.region} from the snapshot")
        inst = self.api.create_instance(region=st.region, plan=st.plan, snapshot_id=ids["snapshot"], label=f"{self.label}-game",
                                        hostname=self.label, sshkey_id=[ids["sshkey"]], firewall_group_id=ids["firewall"],
                                        reserved_ipv4=ids["reserved_ip"], backups="disabled", enable_ipv6=False, tags=[self.label],
                                        user_data=user_data(self.label, self.env["VULTR_API_KEY"], self.env["RCON_PASSWORD"], st))
        inst = self._wait_instance(inst["id"])
        self.api.attach_block(ids["block"], inst["id"])
        ip = ids["reserved_ip"]
        self.log(f"server booted on {ip}; the world volume is attached, Minecraft is starting (1-3 min)")

        def probe():
            try:
                return players_online(self._rcon(ip, "list")) is not None
            except OSError:
                return False
        self.wait("minecraft", probe, 600, every=10)
        self.log(f"ready: {ip}:25565 (auto-off after {st.idle_minutes} idle minutes)")
        return inst

    def down(self, force: bool = False) -> bool:
        ids = self.state.ids
        live = self.running()
        if not live:
            self.log("nothing is running")
            return False
        inst = live[0]
        ip = ids.get("reserved_ip") or inst["main_ip"]
        if not force:
            try:
                self._rcon(ip, "say Server is shutting down now. See you next time!")
                self._rcon(ip, "stop")
                self.log("stop sent; the agent saves the world, detaches the volume and deletes the server")
            except OSError as e:
                self.log(f"rcon not answering ({e}); deleting the server directly")
                force = True
        if force:
            try:
                self.api.detach_block(ids["block"])
            except VultrError:
                pass
            self.api.delete_instance(inst["id"])
        self.wait("the server to disappear", lambda: self.api.instance(inst["id"]) is None, 600, every=10)
        self.log("down: billing stopped; the world is on the volume")
        return True

    def status(self) -> dict:
        ids, st = self.state.ids, self.state
        out = {"region": st.region, "plan": st.plan, "address": ids.get("reserved_ip"), "snapshot": ids.get("snapshot"),
               "snapshot_bundle": ids.get("snapshot_bundle"), "running": None, "players": None, "hours": None, "cost_usd": None}
        if "block" in ids:
            b = self.api.block(ids["block"])
            out["volume"] = {"size_gb": b.get("size_gb"), "status": b.get("status"), "attached": bool(b.get("attached_to_instance"))}
        live = self.running()
        if live:
            inst = live[0]
            out["running"] = {"id": inst["id"], "ip": inst["main_ip"], "since": inst.get("date_created")}
            try:
                out["players"] = players_online(self._rcon(ids.get("reserved_ip") or inst["main_ip"], "list"))
            except OSError:
                out["players"] = "server still starting"
            created = inst.get("date_created")
            if created:
                t0 = time.mktime(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
                hours = max(1, int((time.time() - t0) // 3600) + 1)
                out["hours"] = hours
                monthly = st.extra.get("plan_monthly_usd")
                if monthly:
                    out["cost_usd"] = round(hours * monthly / 730, 2)
        return out

    def teardown(self):
        """Delete everything setup created, including the world volume. Irreversible."""
        ids = self.state.ids
        if self.running():
            self.down(force=True)
        for key, fn in (("snapshot", self.api.delete_snapshot), ("block", self.api.delete_block), ("reserved_ip_id", self.api.delete_reserved_ip)):
            if key in ids:
                fn(ids[key])
                self.log(f"deleted {key} {ids[key]}")
        for key in ("snapshot", "snapshot_bundle", "block", "reserved_ip", "reserved_ip_id"):
            ids.pop(key, None)
        self.save()


# --- command line ---------------------------------------------------------------------------------------------

def _pack(args) -> Pack:
    d = Path(args.pack) if args.pack else find_pack_dir(Path.cwd())
    if d is None:
        sys.exit("no pack.json found here; pass --pack <dir>")
    return load_pack(d)


def _cloud(args) -> Cloud:
    pack = _pack(args)
    d = cloud_dir(pack)
    env = load_env(d / ".env")
    if "VULTR_API_KEY" not in env:
        sys.exit(f"put VULTR_API_KEY=... into {d / '.env'} (Vultr → Account → API). Never paste it in chat.")
    if "RCON_PASSWORD" not in env:
        env["RCON_PASSWORD"] = secrets.token_urlsafe(24)
        with (d / ".env").open("a") as f:
            f.write(f"RCON_PASSWORD={env['RCON_PASSWORD']}\n")
    state = CloudState.load(d / "cloud.json")
    return Cloud(pack, Vultr(env["VULTR_API_KEY"]), env, state)


def cmd_init(args):
    pack = _pack(args)
    d = cloud_dir(pack)
    state = CloudState.load(d / "cloud.json")
    for k in ("region", "plan", "volume_gb", "idle_minutes", "grace_minutes"):
        v = getattr(args, k)
        if v is not None:
            setattr(state, k, v)
    state.save(d / "cloud.json")
    env_path = d / ".env"
    if not env_path.exists():
        env_path.write_text("# Vultr → Account → API → Personal Access Token. Keep this file private.\nVULTR_API_KEY=\n")
        os.chmod(env_path, 0o600)
    print(f"{d / 'cloud.json'}: region={state.region} plan={state.plan} volume={state.volume_gb}GB idle={state.idle_minutes}min")
    print(f"next: paste your API key into {env_path}, then `setup`")


def _public_key() -> str:
    for name in ("id_ed25519.pub", "id_rsa.pub", "id_ecdsa.pub"):
        p = Path.home() / ".ssh" / name
        if p.exists():
            return p.read_text().strip()
    sys.exit("no ssh public key in ~/.ssh; run: ssh-keygen -t ed25519")


def cmd_setup(args):
    c = _cloud(args)
    pack = c.pack
    bundle_zip = Path(args.bundle) if args.bundle else pack.dir / "dist" / f"{pack.name}-{pack.version}-server.zip"
    if not bundle_zip.exists():
        sys.exit(f"{bundle_zip} not found; run `packloom bundle server` first")
    report = pack.dir / "build-report.json"
    loader_version = json.loads(report.read_text())["loader_version"] if report.exists() else None
    if not loader_version:
        sys.exit("build-report.json missing; run `packloom build` first")
    c.setup(bundle_zip, loader_version, _public_key(), rebuild=args.rebuild)


def cmd_up(args):
    _cloud(args).up()


def cmd_down(args):
    _cloud(args).down(force=args.force)


def cmd_status(args):
    s = _cloud(args).status()
    if args.json:
        print(json.dumps(s, indent=2))
        return
    if s["running"]:
        print(f"UP  {s['address']}:25565  players: {s['players']}  running ~{s['hours']} h, ~${s['cost_usd']} so far")
    else:
        print(f"DOWN  address {s['address']}  (volume {s.get('volume', {}).get('size_gb')} GB, snapshot {'ready' if s['snapshot'] else 'missing: run setup'})")


def cmd_teardown(args):
    if not args.yes:
        sys.exit("this deletes the snapshot, the reserved IP and the WORLD volume; pass --yes if that is what you want")
    _cloud(args).teardown()


def main(argv=None):
    p = argparse.ArgumentParser(prog="packloom.cloud", description="an on-demand Vultr server that exists only while people play")
    p.add_argument("--pack")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init", help="write cloud/cloud.json and an empty cloud/.env"); s.set_defaults(fn=cmd_init)
    s.add_argument("--region"); s.add_argument("--plan"); s.add_argument("--volume-gb", dest="volume_gb", type=int)
    s.add_argument("--idle-minutes", dest="idle_minutes", type=int); s.add_argument("--grace-minutes", dest="grace_minutes", type=int)
    s = sub.add_parser("setup", help="volume, reserved IP, firewall and a snapshot with the server installed"); s.set_defaults(fn=cmd_setup)
    s.add_argument("--bundle", help="server zip (default: dist/<name>-<version>-server.zip)"); s.add_argument("--rebuild", action="store_true")
    s = sub.add_parser("up", help="deploy the snapshot, attach the world, start Minecraft"); s.set_defaults(fn=cmd_up)
    s = sub.add_parser("down", help="stop Minecraft and delete the server (the world stays on the volume)"); s.set_defaults(fn=cmd_down)
    s.add_argument("--force", action="store_true", help="delete without a clean stop")
    s = sub.add_parser("status", help="is it up, who is on, what it cost so far"); s.set_defaults(fn=cmd_status); s.add_argument("--json", action="store_true")
    s = sub.add_parser("teardown", help="delete snapshot, reserved IP and the world volume"); s.set_defaults(fn=cmd_teardown); s.add_argument("--yes", action="store_true")
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
