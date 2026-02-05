# SusNet Next Architecture (Draft)

## Design goal
Run a parallel `v2` containerized platform while leaving `v1` untouched until cutover.

## Module boundaries
- `v1-legacy-adapter`: bridge and migration helpers from current host services.
- `core-api`: unified API and auth boundary.
- `ui`: operator UI and setup workflows.
- `bootstrap-api`: first-boot setup flow (`susnet.setup` AP onboarding).
- `gmrs-updater`: controlled extnodes update and validation.
- `aprs`: APRS ingest/send module (planned).
- `meshtastic`: mesh ingest/send module (planned).
- `voip`: Asterisk/ASL integration module (planned).
- `node-red`: orchestration and automations.
- `chirpstack`: LoRaWAN services.
- `portainer`: operations control plane.
- `support-bundle`: diagnostics capture and export.

## Runtime intent
- Portainer manages SusNet Next as separate app stacks (one compose per app).
- Node-RED provides cross-module event workflows.
- Each protocol module reports through API contracts, not direct UI coupling.

## Current stack split
- Bootstrap container:
  - `susnet-next-portainer` (not self-managed inside a Portainer stack)
- Stack: `susnet-admin`
  - `susnet-next-nodered`
- Stack: `susnet-chirpstack`
  - `susnet-next-chirpstack`
  - `susnet-next-chirpstack-gw-bridge`
  - `susnet-next-mosquitto`
  - `susnet-next-postgres`
  - `susnet-next-redis`

## Node-RED seeded flow pack (v2)
- Editor runtime tab:
  - SusNet Runtime
- Dashboard pages:
  - Home
  - AllStar
  - GMRSHub
  - APRS
  - Meshtastic
  - Admin

## Cutover intent
- Validate v2 in parallel.
- Move one module at a time behind feature flags.
- Preserve rollback path to v1.
