# SusNet Next Local Guide

## 1) Confirm stack health
Run:

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl -sS http://127.0.0.1:8090/api/health
```

Expected:
- Containers are `Up`
- Gateway `ok=true`

## 2) Operator URLs
- Portainer: `https://susnet.local:9444`
- Node-RED editor: `http://susnet.local:1881`
- Node-RED dashboard: `http://susnet.local:1881/ui/`
- Core API: `http://susnet.local:8090`
- ChirpStack: `http://susnet.local:8081`

## 3) Inbound readiness checks (AllStar + GMRS)

### AllStar
```bash
curl -sS http://susnet.local:8090/api/allstar/inbound/health
curl -sS -X POST -H 'content-type: application/json' \
  -d '{"duration":45}' \
  http://susnet.local:8090/api/allstar/inbound/test-window
```

### GMRSHub
```bash
curl -sS http://susnet.local:8090/api/gmrshub/inbound/health
curl -sS -X POST -H 'content-type: application/json' \
  -d '{"duration":45}' \
  http://susnet.local:8090/api/gmrshub/inbound/test-window
```

Interpretation:
- `healthy/public-reachable` = inbound packets observed during test window.
- `L2 Router NAT/forward mismatch` = registered/listening but inbound packets not observed.

## 4) Manual GMRS extnodes refresh
- Node-RED dashboard button: `GMRSHub -> Refresh GMRS List`
- or API:

```bash
curl -sS -X POST http://susnet.local:8090/api/allstar/refresh-extnodes
```

## 5) Baseline diagnostics snapshot script

```bash
/home/gabe0000/susnet-next/scripts/collect_inbound_baseline.sh
```

Outputs to `/home/gabe0000/backups/inbound-checks-<timestamp>/`.

## 6) Restart only affected components

```bash
sudo systemctl restart susnet-api
sudo docker restart susnet-module-allstar susnet-module-gmrshub susnet-core-api
sudo docker restart susnet-next-nodered
```

## 7) Public browser access (UI)
SusNet browser UI can be exposed using Tailscale Funnel to Apache (`http://127.0.0.1:80`) while preserving auth at `/susnet/`.
This is for UI management access and is separate from IAX inbound behavior.
