# module-gmrshub

GMRSHub V2 module API proxy.

## Endpoints
- `GET /health`
- `GET /status`
- `GET /nodes`
- `GET /extnodes?node=<id>&limit=<n>`
- `POST /refresh-extnodes`
- `GET /inbound/health`
- `POST /inbound/test-window`

This module exposes GMRS-specific diagnostics through the same gateway model as AllStar.
