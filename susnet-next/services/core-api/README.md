# core-api

SusNet V2 gateway API.

## Role
- Single API entry for UI and Node-RED (`/api/*`).
- Proxies module APIs and normalizes responses.
- Exposes inbound diagnostics surfaces for AllStar/GMRSHub.

## Key diagnostics endpoints
- `GET /api/allstar/inbound/health`
- `POST /api/allstar/inbound/test-window`
- `GET /api/gmrshub/inbound/health`
- `POST /api/gmrshub/inbound/test-window`
