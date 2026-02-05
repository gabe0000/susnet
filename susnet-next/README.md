# SusNet Next (Parallel Refactor)

This workspace is the next-generation stack buildout and does **not** replace your live v1 system.

## Included in this phase
- Portainer (container management control plane)
- `susnet-admin` stack (Node-RED)
- `susnet-chirpstack` stack (ChirpStack + Redis + Postgres + Mosquitto + Gateway Bridge)

## Stack Model
- Portainer runs as its own bootstrap container.
- Each app has its own compose file (one YAML per app stack):
  - `ops/stacks/susnet-admin.compose.yml`
  - `ops/stacks/susnet-chirpstack.compose.yml`

## Access
- Portainer: `https://<pi-ip>:9444`
- Node-RED: `http://<pi-ip>:1881`
- Node-RED Dashboard: `http://<pi-ip>:1881/ui/`
- ChirpStack: `http://<pi-ip>:8081`

## Notes
- This stack uses non-default host ports to avoid conflict with current services.
- v1 remains independent and can continue running while this is developed.
- On Debian images with legacy compose, use `docker-compose` (hyphen).
- Production-like local operation is now via Portainer stacks:
  - `susnet-admin`
  - `susnet-chirpstack`
- See `docs/GETTING_STARTED_LOCAL.md`.
