# SusNet Quick Start (Human‑Friendly)

## Goal
Get the SusNet v2 stack running fast, confirm the UI works, and know where to click.

## 1) Open the control plane
- Portainer: `https://susnet.local:9444`
- Node‑RED: `http://susnet.local:1881`
- Node‑RED Dashboard: `http://susnet.local:1881/ui/`
- Core API (gateway): `http://susnet.local:8090`

## 2) Check the main services
From Portainer → Stacks:
- `susnet-admin` (Node‑RED)
- `susnet-core` (core API + module APIs)
- `susnet-chirpstack` (LoRaWAN services)

Confirm each stack is **Running**.

## 3) Verify health
Open in a browser:
- `http://susnet.local:8090/api/health`
- You should see `ok: true` and modules marked true.

## 4) Use the dashboard
Go to `http://susnet.local:1881/ui/`
- **Home**: overall status
- **AllStar / GMRSHub**: nodes + extnodes
- **APRS**: config + messages
- **Meshtastic**: messages + telemetry
- **Admin**: tickets and controls

## 5) Manual GMRS extnodes refresh
In the Node‑RED dashboard:
- Tab **GMRSHub** → click **Refresh GMRS List**

## 6) If something looks down
- Portainer → Stacks → Recreate
- Or restart key services:
```bash
sudo systemctl restart susnet-api
sudo systemctl restart meshtastic-listener
sudo systemctl restart aprs-listener
sudo systemctl restart asterisk
```

## 7) Backup (safe default)
See `BuildFiles/BackupAndRecovery.md` for one‑command backup + restore.
