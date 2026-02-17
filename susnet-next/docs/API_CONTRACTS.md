# SusNet V2 API Contracts

## Common module envelope
```json
{ "ok": true, "data": { ... }, "errors": [] }
```

## Core gateway principles
- UI and Node-RED consume only `/api/*` routes from `core-api`.
- Module internals remain behind gateway boundaries.

## AllStar / GMRSHub diagnostics contract

### Endpoints
- `GET /api/allstar/inbound/health`
- `POST /api/allstar/inbound/test-window`
- `GET /api/gmrshub/inbound/health`
- `POST /api/gmrshub/inbound/test-window`

### `GET .../inbound/health` response
```json
{
  "ok": true,
  "registered": true,
  "registry_rows": [],
  "perceived_endpoint": "x.x.x.x:port",
  "public_ip": "x.x.x.x",
  "udp_4569_listening": true,
  "extnodes_file": "/var/lib/asterisk/rpt_extnodes_gmrs",
  "extnodes_mtime": "ISO-8601",
  "classification": "L2 Router NAT/forward mismatch",
  "last_inbound_packet_ts": "ISO-8601|null"
}
```

### `POST .../inbound/test-window` request
```json
{ "duration": 45 }
```

### `POST .../inbound/test-window` response
```json
{
  "ok": true,
  "duration": 45,
  "packet_count": 0,
  "last_inbound_packet_ts": null,
  "stderr": ""
}
```

## Existing gateway endpoints retained
- All previous `/api/allstar/*`, `/api/gmrshub/*`, `/api/aprs/*`, `/api/meshtastic/*` routes remain active.

## Meshtastic naming contract
- node-bearing payloads should include:
  - `shortName`
  - `longName`
  - `displayName` (`shortName>longName`)
