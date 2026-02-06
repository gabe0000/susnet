# Node-RED Service

Purpose:
- Workflow automation for SusNet modules.
- Event routing, transforms, and operator tooling.

Data paths:
- Runtime data: `/home/gabe0000/susnet-next/data/nodered`
- Versioned starter flows: `/home/gabe0000/susnet-next/services/node-red/flows`

Default URL:
- `http://<pi-ip>:1881`
- Dashboard URL: `http://<pi-ip>:1881/ui/`

Planned use:
- Ticket workflow hooks
- Cross-module event bus fanout
- Setup wizard backend glue logic

Seeded flow pack (v2-only):
- Main runtime tab in editor: `SusNet Runtime`
- Dashboard pages:
  - Home
  - AllStar
  - GMRSHub
  - APRS
  - Meshtastic
  - Admin
- Flow file (v2-only, gateway based):
  - `/home/gabe0000/susnet-next/services/node-red/flows/susnet_flows_v2.json`
- Runtime backup captured before v2 seed:
  - `/home/gabe0000/susnet-next/data/nodered/flows.pre_v2.backup.json`

Flow seed script:
- `/home/gabe0000/susnet-next/scripts/seed_nodered_flows.sh`
- Supports optional argument:
  - `./scripts/seed_nodered_flows.sh /path/to/custom_flows.json`
