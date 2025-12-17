# Hardening Plan (apply incrementally)

## Secrets & Credentials
- Move secrets into protected env files (root/asterisk readable):
  - /etc/asterisk/manager.conf (admin, allmon3, susnet-monitor)
  - /etc/asterisk/iax.conf (register lines, user secrets)
  - /etc/asterisk/rpt_http_registrations.conf (AllStar/GMRS register passwords)
  - /etc/default/aprs-listener (APRS creds/targets)
  - Cron GMRS fetch URL (currently plain HTTP)
- Rotate obvious/default passwords; avoid reusing the same secret across users.
- Ensure secrets are not committed to git (only env templates with comments).

## Service Exposure
- Bind susnet-api to 127.0.0.1 and front with a proxy/auth (or firewall if LAN-only). Current: 0.0.0.0:8088.
- Keep AMI on 127.0.0.1 (already set). Manager users should be least-privilege per role (UI vs monitor).
- Restrict SSH: key-only auth, fail2ban, and limit to trusted subnets if possible.

## Systemd Hardening (susnet-api)
- Add: NoNewPrivileges=yes, ProtectSystem=full, ProtectHome=true, PrivateTmp=true.
- Drop privileges: run as a dedicated non-root user if write paths are known/limited.
- Set RuntimeDirectory= if the API needs writable temp/state; otherwise keep read-only.

## File Permissions
- /etc/asterisk: root-owned; ensure 0640 where possible; manager.conf/iax.conf/rpt_http_registrations.conf not world-readable.
- /var/lib/asterisk/rpt_extnodes* : asterisk:asterisk 0644 (already enforced by cron for GMRS file).
- Env files (/etc/default/*) should be 0640 root:root (or root:asterisk if the service reads them directly).

## Network Fetch (GMRS extnodes)
- Source: http://66.135.20.206/nodes/nodes.pl -> /var/lib/asterisk/rpt_extnodes_gmrs.
- Prefer HTTPS/checksum if available; otherwise log failures and keep last-known-good.

## Logging & Publishing
- Before publishing logs, scrub callsigns/IDs/secrets. Keep debug levels minimal in prod.

## Cleanup / Redundancy
- Identify and archive/remove unused scripts and stale backups in /home/gabe0000 (aioc* fw scripts, duplicate UPS files, unused meshtastic backups) after confirming they’re not in use.
- Consider pruning unused tmp-docs clones once pushed.

## Image/Replication Prep (later)
- Build an install script (Ansible/bash) that: installs deps, lays down configs from templates, prompts for secrets, sets permissions, enables services, and configures cron for GMRS extnodes.
- Provide a guided setup doc + comprehensive user manual for Pi deployment.
