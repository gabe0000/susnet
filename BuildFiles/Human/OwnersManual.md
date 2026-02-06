# SusNet Owner’s Manual (Plain English)

## What this box does
SusNet is a small always‑on comms hub that collects traffic from:
- AllStar / GMRSHub (voice linking)
- APRS (packet messages)
- Meshtastic (LoRa mesh)
- Plus supporting services (TTS, dashboards, logging)

It lets you see everything in one place and gives you a path to automate it.

## What runs where
- **V1 (host)**: legacy services still running on the Pi
- **V2 (containers)**: new architecture living in Portainer stacks

V2 is being built in parallel so the system stays usable while we migrate.

## Important URLs
- Portainer: `https://susnet.local:9444`
- Node‑RED: `http://susnet.local:1881`
- Node‑RED Dashboard: `http://susnet.local:1881/ui/`
- Core API: `http://susnet.local:8090`
- ChirpStack: `http://susnet.local:8081`

## Daily operator flow
1. Check Portainer: all stacks should be **Running**.
2. Open Node‑RED Dashboard for status + activity.
3. Refresh GMRS extnodes if needed.
4. If messages look stale, restart the relevant listener.

## Recovery basics
- Use the backup guide in `BuildFiles/BackupAndRecovery.md`.
- Restore to `/` (root) not just `/home`.
- Restart services after restore.

## Safety
- Keep credentials out of GitHub.
- Rotate API keys and tokens when exposed.
- Use backups before major changes.
