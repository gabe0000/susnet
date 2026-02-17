# SusNet Owner's Manual

## What this system is
SusNet is a local-first communications operations platform that coordinates:
- AllStar + GMRSHub voice linking
- APRS traffic
- Meshtastic traffic
- dashboards, TTS, logging, and troubleshooting workflows

## Operational model
- RF engine stays stable on host.
- V2 control/API/dashboard runs in containers.
- You operate daily through Portainer + Node-RED dashboard + SusNet UI.

## Core URLs
- Portainer: `https://susnet.local:9444`
- Node-RED dashboard: `http://susnet.local:1881/ui/`
- Gateway API: `http://susnet.local:8090`
- Legacy host API: `http://127.0.0.1:8088`

## Daily operator checklist
1. Confirm stacks are running in Portainer.
2. Check gateway health endpoint.
3. Check AllStar/GMRSHub inbound readiness cards.
4. Refresh GMRS extnodes if stale.
5. Verify active links and message feeds.

## Inbound troubleshooting flow (voice)
1. Open `AllStar` and `GMRSHub` inbound readiness panels.
2. If classification is `L2`, verify router UDP 4569 forward and no duplicate forwards.
3. If classification is `L3`, verify host socket/firewall (`ss -lun`, firewall rules).
4. If classification is `L4`, verify IAX auth/contexts and registration state.
5. Run a 45s inbound test window and compare timestamps.

## Guardrails
- No credential values in docs or shared exports.
- Take backup before host config edits.
- Restart only the components you changed.

## Escalation condition
If inbound remains down but registration is healthy, treat as network-edge issue first (NAT/ISP behavior), then peer-side acceptance.
