# SusNet Next (V2 Parallel Platform)

SusNet Next is the containerized V2 platform that runs in parallel with the live host system.
Current strategy: keep RF-critical host Asterisk/app_rpt stable while moving control-plane and API orchestration into containers.

## Active V2 stacks
- `susnet-admin`: Node-RED + dashboard
- `susnet-core`: core API gateway + module APIs (AllStar, GMRSHub, APRS)
- `susnet-meshtastic`: container-owned Meshtastic module
- `susnet-chirpstack`: ChirpStack + Postgres + Redis + Mosquitto + Gateway Bridge

## Access
- Portainer: `https://<pi-ip>:9444`
- Node-RED editor: `http://<pi-ip>:1881`
- Node-RED dashboard: `http://<pi-ip>:1881/ui/`
- Core API gateway: `http://<pi-ip>:8090`
- ChirpStack: `http://<pi-ip>:8081`

## Key architecture rule
UI and Node-RED should call only the core gateway (`/api/*`), not individual module internals.

## Inbound stabilization (local-only, no cloud)
- New diagnostics API paths:
  - `GET /api/allstar/inbound/health`
  - `POST /api/allstar/inbound/test-window`
  - `GET /api/gmrshub/inbound/health`
  - `POST /api/gmrshub/inbound/test-window`
- Layer classification model:
  - `L1 ISP/CGNAT blocked`
  - `L2 Router NAT/forward mismatch`
  - `L3 Host firewall/socket issue`
  - `L4 Asterisk auth/context/codec reject`

## Notes
- V1 host API remains at `http://127.0.0.1:8088` for live compatibility.
- V2 proxies selected V1 capabilities while module-native functions are expanded.
- Secrets stay local; never commit credentials/tokens.
