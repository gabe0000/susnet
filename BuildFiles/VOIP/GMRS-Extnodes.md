# GMRS Extnodes Workflow (531121)

## Purpose
Maintain separate extnodes data sources on one Pi:
- ASL stock: `/var/lib/asterisk/rpt_extnodes`
- GMRS override: `/var/lib/asterisk/rpt_extnodes_gmrs`

## Runtime source of truth
Root cron has one updater entry:

```cron
*/15 * * * * /usr/local/sbin/update_gmrs_extnodes.sh
```

Script path:
- `/usr/local/sbin/update_gmrs_extnodes.sh`

Current behavior:
- download `http://66.135.20.206/nodes/nodes.pl`
- compare with existing file
- replace only when changed
- set owner/group `asterisk:asterisk`
- set mode `0644`
- reload `app_rpt` only when changed

## Manual refresh methods
### API method (preferred)
```bash
curl -sS -X POST http://127.0.0.1:8088/api/allstar/refresh-gmrs-list
```

### Dashboard method
- Node-RED dashboard -> GMRSHub -> `Refresh GMRS List`

### Script method
```bash
sudo /usr/local/sbin/update_gmrs_extnodes.sh
```

## Validation
```bash
ls -l /var/lib/asterisk/rpt_extnodes_gmrs
head -n 20 /var/lib/asterisk/rpt_extnodes_gmrs
sudo asterisk -rx 'module reload app_rpt.so'
```

## Failure patterns
- stale file mtime -> cron not running
- wrong owner/perms -> app_rpt read issues
- duplicate cron entries -> unnecessary churn/reloads
