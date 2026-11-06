#!/usr/bin/env python3
"""Runs on the cloud server, standard library only, Python 3.10+. Copied there by `packloom.cloud setup`.

  boot   read KEY=VALUE user-data from the metadata service, mount the world volume, start the server
  run    every minute: ask the server how many players are on; when the idle policy says so, stop it;
         once the server is down (stopped or crashed), copy logs to the volume, unmount, detach, and delete
         this very instance through the Vultr API, so billing ends without anyone at a keyboard
  rcon   send one command to the local server (used by systemd's ExecStop)

packloom.cloud imports rcon() and players_online() from here, so this file has no packloom imports.
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

ENV_PATH = Path("/etc/techpack.env")
METADATA = "http://169.254.169.254"
API = "https://api.vultr.com/v2"


# --- rcon ------------------------------------------------------------------------------------------------------

def rcon(host: str, port: int, password: str, command: str, timeout: float = 10) -> str:
    """Minecraft RCON: one login, one command, close. Raises OSError when the server is not there yet."""
    def packet(kind: int, payload: str) -> bytes:
        body = struct.pack("<ii", 0, kind) + payload.encode("utf-8") + b"\x00\x00"
        return struct.pack("<i", len(body)) + body

    def read(sock) -> tuple[int, int, str]:
        head = b""
        while len(head) < 4:
            chunk = sock.recv(4 - len(head))
            if not chunk:
                raise OSError("rcon: connection closed")
            head += chunk
        (length,) = struct.unpack("<i", head)
        body = b""
        while len(body) < length:
            chunk = sock.recv(length - len(body))
            if not chunk:
                raise OSError("rcon: connection closed")
            body += chunk
        rid, kind = struct.unpack("<ii", body[:8])
        return rid, kind, body[8:-2].decode("utf-8", "replace")

    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(packet(3, password))
        rid, _, _ = read(s)
        if rid == -1:
            raise PermissionError("rcon: wrong password")
        s.sendall(packet(2, command))
        _, _, text = read(s)
        return text


def players_online(list_output: str) -> Optional[int]:
    """`list` answers "There are 2 of a max of 8 players online: a, b". None when that is not what came back."""
    m = re.search(r"There are (\d+) of a max", list_output)
    return int(m.group(1)) if m else None


# --- the idle policy ------------------------------------------------------------------------------------------

def should_stop(players: int, idle_minutes: float, uptime_minutes: float, idle_limit: int, grace: int) -> bool:
    """Decide whether the server should shut itself down now.

    players         how many are online right now
    idle_minutes    how long nobody has been online (0 when someone is on)
    uptime_minutes  how long this server has existed
    idle_limit      cloud.json idle_minutes (default 30)
    grace           cloud.json grace_minutes (default 15): friends may still be joining right after `up`
    """
    if players > 0 or uptime_minutes < grace:
        return False                       # people on, or friends may still be joining after `up`
    if idle_minutes >= idle_limit:
        return True                        # everybody left a while ago
    # Nobody has joined since boot (idle for as long as the server has been answering, give or take the
    # few minutes Minecraft needs to start): a forgotten `up` should not cost idle_limit on top of grace.
    return idle_minutes >= uptime_minutes - 5


# --- helpers -----------------------------------------------------------------------------------------------------

def load_env(path: Path = ENV_PATH) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def sh(cmd: str, check: bool = False) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}: {r.stderr.strip()}")
    return r.stdout.strip()


def metadata(path: str) -> str:
    with urllib.request.urlopen(METADATA + path, timeout=5) as r:
        return r.read().decode("utf-8", "replace")


def instance_id() -> str:
    data = json.loads(metadata("/v1.json"))
    return data.get("instance-v2-id") or data.get("instanceid")


def api(env: dict, method: str, path: str, body: Optional[dict] = None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {env['VULTR_API_KEY']}", "Content-Type": "application/json",
                                          "User-Agent": "packloom-cloud-agent/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def uptime_minutes() -> float:
    return float(Path("/proc/uptime").read_text().split()[0]) / 60


def unit_active(label: str) -> bool:
    return sh(f"systemctl is-active {label}.service") == "active"


def log(msg: str):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# --- boot -------------------------------------------------------------------------------------------------------

def boot():
    if not ENV_PATH.exists():
        text = ""
        for _ in range(120):               # the metadata service answers within seconds; be patient anyway
            try:
                text = metadata("/latest/user-data")
                if "VULTR_API_KEY=" in text:
                    break
            except OSError:
                pass
            time.sleep(5)
        if "VULTR_API_KEY=" not in text:
            sys.exit("no user-data with VULTR_API_KEY; this server was not created by packloom.cloud up")
        ENV_PATH.write_text(text)
        ENV_PATH.chmod(0o600)
    env = load_env()
    label, mount, vol = env["LABEL"], env["MOUNT"], env["VOLUME_LABEL"]
    for _ in range(120):                   # `up` attaches the volume right after the server reports active
        if sh(f"blkid -L {vol}"):
            break
        time.sleep(5)
    else:
        sys.exit(f"no volume labelled {vol} appeared in 10 minutes")
    if mount not in sh("mount"):
        sh(f"mount -L {vol} {mount}", check=True)
    sh(f"systemctl start {label}.service", check=True)
    sh(f"systemctl start {label}-agent.service", check=True)
    log(f"booted: {vol} on {mount}, {label}.service started")


# --- run ---------------------------------------------------------------------------------------------------------

def finalize(env: dict):
    label, mount, root = env["LABEL"], env["MOUNT"], env["SERVER_ROOT"]
    for _ in range(30):
        if not unit_active(label):
            break
        time.sleep(10)
    else:
        sh(f"systemctl kill {label}.service")
        time.sleep(10)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for sub in ("logs", "crash-reports"):
        src = Path(root) / sub
        if src.is_dir():
            shutil.copytree(src, Path(mount) / "logs" / stamp / sub, dirs_exist_ok=True)
    sh("sync")
    for _ in range(12):
        if sh(f"umount {mount} 2>&1") == "" and mount not in sh("mount"):
            break
        time.sleep(5)
    me = instance_id()
    try:
        api(env, "POST", f"/blocks/{env['BLOCK_ID']}/detach", {"live": True})
    except Exception as e:                 # the instance deletion below detaches it anyway
        log(f"detach: {e}")
    log(f"deleting instance {me}")
    api(env, "DELETE", f"/instances/{me}")


def run():
    env = load_env()
    label = env["LABEL"]
    idle_limit, grace = int(env.get("IDLE_MINUTES", 30)), int(env.get("GRACE_MINUTES", 15))
    started_once, idle_since, stop_sent = False, None, False
    log(f"watching {label}: stop after {idle_limit} idle minutes, never before {grace} minutes of uptime")
    while True:
        up = uptime_minutes()
        if not unit_active(label):
            if started_once or stop_sent or up > grace + 10:
                log("server is down; finalizing")
                finalize(env)
                return
            time.sleep(30)                 # still starting
            continue
        try:
            n = players_online(rcon("127.0.0.1", int(env["RCON_PORT"]), env["RCON_PASSWORD"], "list"))
        except OSError:
            n = None
        if n is None:
            time.sleep(30)
            continue
        started_once = True
        now = time.monotonic()
        idle_since = None if n > 0 else (idle_since or now)
        idle = (now - idle_since) / 60 if idle_since else 0.0
        if not stop_sent and should_stop(n, idle, up, idle_limit, grace):
            log(f"nobody for {idle:.0f} min (uptime {up:.0f}); stopping")
            try:
                rcon("127.0.0.1", int(env["RCON_PORT"]), env["RCON_PASSWORD"], "say Nobody online: shutting down to save money.")
                rcon("127.0.0.1", int(env["RCON_PORT"]), env["RCON_PASSWORD"], "stop")
            except OSError as e:
                log(f"stop via rcon failed ({e}); stopping the unit")
                sh(f"systemctl stop {label}.service")
            stop_sent = True
        time.sleep(60)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("boot", "run", "rcon"):
        sys.exit("usage: cloud_agent.py boot | run | rcon <command...>")
    if argv[0] == "boot":
        boot()
    elif argv[0] == "run":
        run()
    else:
        env = load_env()
        print(rcon("127.0.0.1", int(env["RCON_PORT"]), env["RCON_PASSWORD"], " ".join(argv[1:]) or "list"))


if __name__ == "__main__":
    main()
