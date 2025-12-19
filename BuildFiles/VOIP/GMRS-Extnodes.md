# GMRS/ASL Dual Extnodes (531121)

Purpose: keep AllStarLink nodes on the stock list while 531121 uses the GMRS directory feed, all on the same Pi.

## How it works
- Global extnode file: `/var/lib/asterisk/rpt_extnodes` (ASL/stock). Set in `[general]` of `/etc/asterisk/rpt.conf`.
- 531121 override: in its node stanza use the GMRS list:  
  `extnodefile=/var/lib/asterisk/rpt_extnodes_gmrs`
- Update job (root crontab): runs every 15 minutes to fetch GMRS extnodes. Command:  
  `curl -fsSL http://66.135.20.206/nodes/nodes.pl -o /tmp/rpt_extnodes_gmrs.new && [ -s /tmp/rpt_extnodes_gmrs.new ] && mv /tmp/rpt_extnodes_gmrs.new /var/lib/asterisk/rpt_extnodes_gmrs && chown asterisk:asterisk /var/lib/asterisk/rpt_extnodes_gmrs && chmod 644 /var/lib/asterisk/rpt_extnodes_gmrs && asterisk -rx 'module reload app_rpt.so' >/dev/null 2>&1`
- Ownership/permissions: `asterisk:asterisk`, `0644`.

## Recovery steps
1) Ensure `/etc/asterisk/rpt.conf` has:
   - `[general] extnodefile=/var/lib/asterisk/rpt_extnodes`
   - In `[531121](node-main)`: `extnodefile=/var/lib/asterisk/rpt_extnodes_gmrs`
2) Confirm the GMRS file exists and has entries like `531000=...` at `/var/lib/asterisk/rpt_extnodes_gmrs`.
3) If missing, rerun the cron command once manually (as root), or let cron repopulate within 15 minutes.
4) Reload app_rpt: `asterisk -rx 'module reload app_rpt.so'`.

## Notes
- Do **not** merge the lists; keep ASL and GMRS separate to avoid clobbering.
- If the GMRS URL changes, update the cron job and re-run once.
- Backups live in `/var/asl-backups/`; the 2025-10-06 set contains the known-good rpt.conf with the per-node extnodefile override.
