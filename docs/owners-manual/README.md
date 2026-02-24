# Susnet Owner's Manual

## Canonical State
- Hostname: `susnet`
- Tailscale IPv4: `susnet`
- OS: `Debian GNU/Linux 12 (bookworm)`
- Architecture: `aarch64`

- Primary role:
  - control-plane authority (`Joe Cabot`) for Reservoir Pi(s)

- Active control/runtime components:
  - `openclaw_openclaw-gateway_1` OpenClaw gateway
  - `openclaw-ollama` local model backend
  - `joe-cabot-lite.service` front-desk back-office worker for Mr Pink escalations
  - `susnet-next-mosquitto` broker
  - `susnet-next-nodered` ops automation
  - `susnet-core-api` core API

- Joe runtime source-of-truth:
  - tracked path: `susnet-next/services/joe-cabot-lite/`
  - deployed path: `/home/codex/joe-cabot-lite`
  - deployment command: `./scripts/deploy-joe-cabot-lite.sh`

- OpenClaw exposure model:
  - Docker host publish on `28789` to container `18789`
  - Tailscale TCP serve publishes `18789` to `localhost:28789`
  - Operator endpoint remains `susnet:18789`

- Joe Cabot control topics:
  - `susnet/agent/query`
  - `susnet/agent/reply`
  - `susnet/agent/ack`
  - `susnet/agent/progress`
  - `susnet/agent/control`
  - `susnet/agent/error`
  - `susnet/agent/dlq`

- Joe Cabot consumed edge event topics:
  - `meshbox/agent/events/rx`
  - `meshbox/agent/events/policy`
  - `meshbox/agent/events/health`
  - `meshbox/agent/events/nodes`

- Front-desk timing defaults:
  - ack timeout `7s`
  - response timeout `30s`
  - wait extension `30s`, max `2`
  - wait prompt auto-close `45s`

- Storage layout:
  - Root `/dev/mmcblk0p2` about `100GiB`
  - Data `/dev/mmcblk0p3` mounted at `/data` about `100GiB`

- Canonical architecture repo:
  - `https://github.com/gabe0000/resevoir-pis`

- Last validated: `2026-02-24 14:28 UTC`
- Validator: `scripts/validate-docs.sh v1`

## Definition of Done
- [ ] Runtime/control change applied
- [ ] Verification complete
- [ ] Owner manual + quickstart updated
- [ ] Journal/logbook/changelog updated
- [ ] Validation script passes
