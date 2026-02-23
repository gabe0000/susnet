# Susnet Owner's Manual

## Canonical State
- Hostname: `susnet`
- Tailscale IPv4: `susnet`
- OS: `Debian GNU/Linux 12 (bookworm)`
- Architecture: `aarch64`

- Primary role:
  - control-plane authority (`Joe Cabot`) for Reservoir Pi(s)

- Active control/runtime components:
  - `openclaw_openclaw-gateway_1` (OpenClaw gateway)
  - `openclaw-ollama` (local model backend)
  - `joe-cabot-lite.service` (lightweight MQTT consumer/responder)
  - Conversational mode: dedicated-channel chat support with bounded RF-size responses
  - Fallback model: local rule-based reply when local LLM response does not arrive within timeout budget
  - `susnet-next-mosquitto` (broker)
  - `susnet-next-nodered` (ops automation)
  - `susnet-core-api` (core API)

- OpenClaw exposure model:
  - Docker host publish on `28789` -> container `18789`
  - Tailscale TCP serve publishes `18789` -> `localhost:28789`
  - Operator endpoint remains `susnet:18789`

- Joe Cabot query/reply topics:
  - `susnet/agent/query`
  - `susnet/agent/reply`

- Joe Cabot consumed edge topics:
  - `meshbox/agent/events/rx`
  - `meshbox/agent/events/policy`
  - `meshbox/agent/events/health`
  - `meshbox/agent/events/nodes`

- Storage layout:
  - Root: `/dev/mmcblk0p2` (~100GiB)
  - Data: `/dev/mmcblk0p3` mounted at `/data` (~100GiB)
  - Remaining card tail intentionally unallocated

- Wi-Fi priority order:
  1. `nacho2` (prio 400)
  2. `nacho2_EXT` (prio 300)
  3. `PawPawWireless` (prio 200)
  4. `gabesiphone` (prio 150)
  5. `nacho` (`preconfigured`, prio -100)

- Canonical architecture repo:
  - `https://github.com/gabe0000/resevoir-pis`

- Last validated: `2026-02-23 00:02 UTC`
- Validator: `scripts/validate-docs.sh v1`

## Definition of Done
- [ ] Runtime/control change applied
- [ ] Verification complete
- [ ] Owner manual + quickstart updated
- [ ] Journal/logbook/changelog updated
- [ ] Validation script passes
