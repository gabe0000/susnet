# module-allstar

AllStar V2 module API proxy.

## Endpoints
- `GET /health`
- `GET /status`
- `GET /nodes`
- `GET /extnodes?node=<id>&limit=<n>`
- `POST /refresh-extnodes`
- `GET /inbound/health`
- `POST /inbound/test-window`

This module proxies the host API for live node visibility while keeping V2 contracts stable.
