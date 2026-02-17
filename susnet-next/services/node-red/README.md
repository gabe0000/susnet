# Node-RED Service

## Purpose
- V2 operator dashboard and automation workflows.
- Gateway-only HTTP usage (`http://susnet-core-api:8080/api/...`).

## Paths
- Runtime data: `/home/gabe0000/susnet-next/data/nodered`
- Versioned flow pack: `/home/gabe0000/susnet-next/services/node-red/flows/susnet_flows_v2.json`

## URLs
- Editor: `http://<pi-ip>:1881`
- Dashboard: `http://<pi-ip>:1881/ui/`

## Seed flow pack
```bash
/home/gabe0000/susnet-next/scripts/seed_nodered_flows.sh --direct \
  /home/gabe0000/susnet-next/services/node-red/flows/susnet_flows_v2.json
sudo docker restart susnet-next-nodered
```

## Current dashboard groups
- Home
- AllStar
- GMRSHub
- APRS
- Meshtastic
- Admin

Includes inbound readiness and manual test-window controls for AllStar/GMRSHub.
