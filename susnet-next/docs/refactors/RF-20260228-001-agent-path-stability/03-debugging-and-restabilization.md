# Debugging And Restabilization

Key recurring issues tracked:
1. channel identity confusion when channel index was treated as stable selector
2. callback/path timing causing intermittent relay behavior
3. poll-heavy observability path causing burst load noise

Runtime stabilization actions applied (2026-02-28):
- Upgraded services/core-api/app/main.py mesh read path with:
  - shared pooled HTTP client for backend calls
  - singleflight cache-miss coalescing for cacheable Meshtastic endpoints
  - safer cache TTL defaults tuned for dashboard polling
- Reduced Node-RED dashboard poll inject rates in live and tracked flow files:
  - health/services: 15s -> 30s
  - mesh messages: 15s -> 30s
  - mesh telemetry: 30s -> 45s
  - mesh nodes: 20s -> 45s
  - mesh mqtt status: 20s -> 45s

Measured impact (module-meshtastic requests from core-api over 2-minute sample):
- before: health 8, messages 8, nodes 6, mqtt_status 6, telemetry 4
- after:  health 4, messages 4, nodes 3, mqtt_status 3, telemetry 3

Stabilization stance:
- keep channel index as transport metadata only
- preserve lifecycle ordering and bounded pacing
- continue migration from polling-heavy observability to event-driven delivery where practical

Second runtime stabilization pass (2026-02-28, later wave):
- Identified meshtastic hotspot inside node snapshot/update path:
  - node records were rewritten (and persisted) on repeated snapshots even when data was unchanged
  - `/nodes` endpoint forced live snapshots on every read
- Applied targeted refactor in `services/module-meshtastic/app/main.py`:
  - preserve existing `last_heard` unless explicitly updated by real traffic events
  - write `nodes.json` only when a node record actually changes
  - add optional `refresh` flag on `/nodes` (default cached read)
  - rate-limit connected-state snapshots via `MESH_NODE_SNAPSHOT_SECONDS` (default 15s)
- Operational note:
  - container restart exposed brittle serial device-path pinning when that by-id path is absent
  - temporary placeholder path was used to restore service while TCP path remains primary
