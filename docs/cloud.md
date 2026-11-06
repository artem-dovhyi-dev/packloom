# cloud: a server that exists only while people play

A hosted Minecraft server for a group that plays an hour or two a day should not cost a month of VPS. Vultr bills
by the hour but keeps billing a powered-off server, so the cheap server is one that is **destroyed** between
sessions. `packloom.cloud` makes that a single command each way and lets the server destroy itself.

```
python3 -m packloom.cloud --pack modpack init --region sgp --plan vc2-4c-8gb
#   -> cloud/cloud.json and cloud/.env; paste your Vultr API key into .env
python3 -m packloom.cloud --pack modpack setup       # once, ~20 min: volume, reserved IP, firewall, snapshot
python3 -m packloom.cloud --pack modpack up          # ~5 min: friends join <reserved IP>:25565
python3 -m packloom.cloud --pack modpack status
python3 -m packloom.cloud --pack modpack down        # or just leave: the agent does it after 30 idle minutes
```

## What setup creates

| Thing | Why | Cost while the server is down |
|---|---|---|
| Block storage volume (10 GB NVMe, or 40 GB HDD where NVMe is not sold) | holds `world/`, `ops.json`, whitelist and bans; survives every server | about 1 $/month |
| Reserved IPv4 | friends add the address once | a few $/month, shown in the Vultr panel |
| Snapshot | the server bundle unpacked, Java and the loader installed, systemd units in place; `up` deploys it instead of installing | cents |
| Firewall group | 22/tcp, 25565/tcp, 24454/udp (voice chat) open; RCON stays private | free |
| SSH key | your `~/.ssh/id_*.pub`, for setup and debugging | free |

`setup` builds the snapshot on a throwaway server from `dist/<name>-<version>-server.zip`, so run
`packloom build` and `packloom bundle server` first. After a pack update, `setup --rebuild` makes a new snapshot;
the volume with the world is untouched.

## What happens on `up`

1. A server is created from the snapshot with the reserved IP and a small KEY=VALUE **user-data** (API key,
   RCON password, idle policy).
2. The volume is attached. `<label>-boot.service` on the server reads the user-data from the metadata
   service into `/etc/techpack.env`, waits for the volume, mounts it and starts Minecraft.
3. `up` polls RCON until the server answers `list`, then prints the address.

## What the agent does

`cloud_agent.py` runs as `<label>-agent.service` next to Minecraft:

- every minute it asks RCON how many players are on;
- `should_stop(players, idle_minutes, uptime_minutes, idle_limit, grace)` decides when to shut down
  (`idle_minutes` and `grace_minutes` in cloud.json);
- when Minecraft is down for any reason (stop, crash, `down` from your laptop) it copies `logs/` and
  `crash-reports/` to the volume, unmounts, detaches the volume and deletes its own instance through the API.

The API key therefore lives on the server (root-only, for the hours the server exists). That is the price of a
server that can delete itself; a sub-account key limited to this project would be better if Vultr offers one.

## Files

```
<pack>/cloud/
  cloud.json    region, plan, volume size, idle policy, and the ids setup created (commit this)
  .env          VULTR_API_KEY, RCON_PASSWORD (never commit; .gitignore is written for you)
```

`teardown --yes` deletes the snapshot, the reserved IP and the volume with the world. Download the world first
if you want it.
