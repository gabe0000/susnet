# SusNet Quick Start

## Fast startup
1. Open Portainer: `https://susnet.local:9444`
2. Confirm stacks:
   - `susnet-admin`
   - `susnet-core`
   - `susnet-meshtastic`
   - `susnet-chirpstack`
3. Open dashboard: `http://susnet.local:1881/ui/`
4. Check API: `http://susnet.local:8090/api/health`

## Fast inbound check

```bash
curl -sS http://susnet.local:8090/api/allstar/inbound/health
curl -sS http://susnet.local:8090/api/gmrshub/inbound/health
```

## Run manual capture window

```bash
curl -sS -X POST -H 'content-type: application/json' \
  -d '{"duration":45}' \
  http://susnet.local:8090/api/allstar/inbound/test-window
```

## Refresh GMRS extnodes
- Dashboard button: `Refresh GMRS List`
- API fallback:

```bash
curl -sS -X POST http://susnet.local:8090/api/allstar/refresh-extnodes
```

## If things look broken
1. Restart `susnet-api` (host).
2. Restart `susnet-module-allstar`, `susnet-module-gmrshub`, `susnet-core-api`.
3. Restart Node-RED container.
4. Re-run inbound health endpoints.
