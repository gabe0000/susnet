# Backup and Recovery (Simple Guide)

This is a plain‑English guide to back up SusNet and restore it if something goes wrong.

## What this covers
- Making a safe backup of your important SusNet files.
- How to copy that backup off the Pi.
- How to restore from a backup.

## Quick backup (safe default)
This backup skips caches/venv/runtime data. It is good for configuration and rebuilds.

```bash
TS=$(date +%Y%m%d-%H%M%S)
BACK=/home/gabe0000/backups/susnet-full-${TS}.tgz
sudo tar -czf "$BACK" \
  --exclude='/home/gabe0000/**/venv' \
  --exclude='/home/gabe0000/.cache' \
  --exclude='/home/gabe0000/.codex' \
  --exclude='/home/gabe0000/.vscode-server' \
  --exclude='/home/gabe0000/**/__pycache__' \
  --exclude='/home/gabe0000/susnet-next/data' \
  /home/gabe0000/susnet-next \
  /home/gabe0000/BuildFiles \
  /home/gabe0000/Journal \
  /home/gabe0000/meshtastic \
  /home/gabe0000/aprs \
  /home/gabe0000/private-ui \
  /home/gabe0000/susnet_api.py \
  /etc/asterisk \
  /var/lib/asterisk \
  /var/lib/susnet \
  /opt/susnet-api

ls -lah "$BACK"
```

## Full backup (includes live data)
Only do this if you need full state recovery (DBs, runtime data). The file will be bigger.

```bash
TS=$(date +%Y%m%d-%H%M%S)
BACK=/home/gabe0000/backups/susnet-full-with-data-${TS}.tgz
sudo tar -czf "$BACK" \
  --exclude='/home/gabe0000/**/venv' \
  --exclude='/home/gabe0000/.cache' \
  --exclude='/home/gabe0000/.codex' \
  --exclude='/home/gabe0000/.vscode-server' \
  --exclude='/home/gabe0000/**/__pycache__' \
  /home/gabe0000/susnet-next \
  /home/gabe0000/BuildFiles \
  /home/gabe0000/Journal \
  /home/gabe0000/meshtastic \
  /home/gabe0000/aprs \
  /home/gabe0000/private-ui \
  /home/gabe0000/susnet_api.py \
  /etc/asterisk \
  /var/lib/asterisk \
  /var/lib/susnet \
  /opt/susnet-api

ls -lah "$BACK"
```

## Copy backup to your Mac
Run this on your Mac terminal (not inside SSH):

```bash
scp gabe0000@susnet.local:/home/gabe0000/backups/susnet-full-YYYYMMDD-HHMMSS.tgz ~/Downloads/
```

If `susnet.local` doesn’t work, use the Pi IP.

## Restore (basic)
1. Copy the backup file back to the Pi.
2. Extract it to root:

```bash
sudo tar -xzf /home/gabe0000/backups/your-backup-file.tgz -C /
```

3. Restart services if needed:

```bash
sudo systemctl restart susnet-api
sudo systemctl restart meshtastic-listener
sudo systemctl restart aprs-listener
sudo systemctl restart asterisk
```

4. If using containers, restart stacks via Portainer or:

```bash
sudo docker-compose -f /home/gabe0000/susnet-next/ops/stacks/susnet-admin.compose.yml up -d
sudo docker-compose -f /home/gabe0000/susnet-next/ops/stacks/susnet-core.compose.yml up -d
sudo docker-compose -f /home/gabe0000/susnet-next/ops/stacks/susnet-chirpstack.compose.yml up -d
```

## Common recovery mistakes
- Restoring into `/home/gabe0000` only instead of `/` (wrong paths).
- Forgetting to restart services after restore.
- Overwriting newer config files without a second copy.

## Notes
- Keep backups off the Pi (USB drive or your laptop).
- Do not store credentials in GitHub.
