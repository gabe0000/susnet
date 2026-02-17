# Backup and Recovery

## Before major network/voice changes
Always create a timestamped rollback bundle:

```bash
TS=$(date +%Y%m%d-%H%M%S)
sudo tar -czf /home/gabe0000/backups/susnet-prechange-${TS}.tgz \
  /etc/asterisk \
  /var/lib/asterisk/rpt_extnodes \
  /var/lib/asterisk/rpt_extnodes_gmrs \
  /opt/susnet-api \
  /home/gabe0000/susnet-next
```

## Inbound hardening snapshot used in this cycle
- `/home/gabe0000/backups/susnet-pre-inbound-hardening-<timestamp>.tgz`
- `/home/gabe0000/backups/inbound-hardening-<timestamp>/`

## Baseline collection script
```bash
/home/gabe0000/susnet-next/scripts/collect_inbound_baseline.sh
```

## Restore steps
1. Place backup file on Pi.
2. Restore to root:

```bash
sudo tar -xzf /home/gabe0000/backups/<backup>.tgz -C /
```

3. Restart affected services:

```bash
sudo systemctl restart asterisk
sudo systemctl restart susnet-api
sudo docker restart susnet-module-allstar susnet-module-gmrshub susnet-core-api susnet-next-nodered
```

4. Validate:

```bash
curl -sS http://127.0.0.1:8088/api/health
curl -sS http://127.0.0.1:8090/api/health
```
