# SusNet V2 API Contracts (Draft)

## Common module response envelope
```json
{ "ok": true, "data": { ... }, "errors": [] }
```

## Module APIs (internal)

### AllStar API (`module-allstar`)
- `GET /health`
- `GET /status`
- `GET /nodes`
- `GET /extnodes?node=<id>&limit=<n>`
- `POST /refresh-extnodes`

### GMRSHub API (`module-gmrshub`)
- `GET /health`
- `GET /status`
- `GET /nodes`
- `GET /extnodes?node=<id>&limit=<n>`
- `POST /refresh-extnodes`

### APRS API (`module-aprs`)
- `GET /health`
- `GET /config`
- `GET /messages`
- `POST /send`
- `POST /config`

### Meshtastic API (`module-meshtastic`)
- `GET /health`
- `GET /messages`
- `GET /telemetry`
- `POST /send`

## Core API Gateway (external)

- `GET /api/health`
- `GET /api/services` (proxy to v1 services for now)
- `GET /api/tickets` (proxy to v1 tickets for now)
- `GET /api/allstar/nodes`
- `GET /api/allstar/extnodes?node=<id>&limit=<n>`
- `POST /api/allstar/refresh-extnodes`
- `GET /api/gmrshub/nodes`
- `GET /api/gmrshub/extnodes?node=<id>&limit=<n>`
- `POST /api/gmrshub/refresh-extnodes`
- `GET /api/aprs/config`
- `GET /api/aprs/messages`
- `POST /api/aprs/send`
- `GET /api/meshtastic/messages`
- `GET /api/meshtastic/telemetry`
- `POST /api/meshtastic/send`

### Gateway response shape
Gateway responses are v1-compatible where practical to reduce UI churn.

- `GET /api/allstar/nodes` returns `{ok, nodes:[...]}`
- `GET /api/allstar/extnodes` returns `{ok, entries:[...], count}`
- Other endpoints pass through the underlying v1 data, wrapped in `ok`.
