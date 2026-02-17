# Replication Guide

## Goal
Rebuild a functionally equivalent SusNet node with clear operator setup.

## High-level build order
1. Base OS + networking
2. Host Asterisk + ASL node config
3. Host `susnet-api` (v1 adapter)
4. V2 containers (`susnet-next` stacks)
5. Dashboard + docs + backup automation

## Required service groups
- Host RF engine:
  - `asterisk`
  - host IAX config + extnodes files
- Host adapter:
  - `susnet-api` on 8088
- V2 stacks:
  - admin, core, meshtastic, chirpstack

## Required local paths
- `/etc/asterisk`
- `/var/lib/asterisk/rpt_extnodes*`
- `/opt/susnet-api`
- `/home/gabe0000/susnet-next`
- `/home/gabe0000/BuildFiles`
- `/home/gabe0000/Troubleshooting`
- `/home/gabe0000/Journal`

## Inbound requirements for public IAX reachability
- Static/DHCP-reserved LAN IP for Pi
- UDP 4569 forwarded to Pi
- No competing port-forward entries
- SIP ALG/helper disabled

## Validation checklist
- `iax2 show registry` registered states present
- Gateway `/api/allstar/inbound/health` responds
- GMRS extnodes refresh works and ownership remains `asterisk:asterisk`
- Node-RED dashboard displays inbound readiness blocks
