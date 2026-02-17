# SusNet Next Architecture

## Design intent
- Keep live RF stable on host.
- Containerize control plane aggressively.
- Isolate module APIs and keep UI/gateway dependency clean.

## Runtime split
- Host production (RF-critical): Asterisk/app_rpt, iax, extnodes files.
- Host service: V1 API (`susnet-api` on 8088) with direct Asterisk/system visibility.
- Containers (V2): core gateway + module APIs + Node-RED + ChirpStack.

## Stack inventory
- `susnet-admin`
  - `susnet-next-nodered`
- `susnet-core`
  - `susnet-core-api`
  - `susnet-module-allstar`
  - `susnet-module-gmrshub`
  - `susnet-module-aprs`
- `susnet-meshtastic`
  - `susnet-module-meshtastic`
- `susnet-chirpstack`
  - `susnet-next-chirpstack`
  - `susnet-next-chirpstack-gw-bridge`
  - `susnet-next-mosquitto`
  - `susnet-next-postgres`
  - `susnet-next-redis`

## Inbound diagnostics architecture
- V1 host API implements low-level inbound checks:
  - `iax2 show registry` parsing
  - UDP 4569 listener check (`ss -lun`)
  - extnodes metadata
  - optional test-window packet capture (when tcpdump available)
- V2 modules proxy V1 diagnostics.
- V2 core exposes canonical endpoints for UI/Node-RED.

## Failure taxonomy
- `L1 ISP/CGNAT blocked`
- `L2 Router NAT/forward mismatch`
- `L3 Host firewall/socket issue`
- `L4 Asterisk auth/context/codec reject`

## Safety model
- No destructive auto-remediation in diagnostics endpoints.
- classify + timestamp + operator action only.
- Rollback bundles generated before host config edits.
