# Agent Ops Guide

## Operating posture
- Local-only architecture; no cloud relay unless explicitly approved.
- Containerize control-plane modules where possible.
- Host Asterisk remains production until a dedicated migration cycle.

## Mandatory guardrails
- No destructive git reset/checkout operations.
- No secrets in docs, commits, tickets, or exports.
- No broad restarts for narrow changes.
- Preserve user-created files and tuning unless explicitly instructed.

## Inbound stabilization runbook
1. Backup + baseline capture.
2. Apply minimal host config edits (if required) with rollback artifact.
3. Wire diagnostics endpoints:
   - host API -> module APIs -> core gateway
4. Update Node-RED dashboard controls and status blocks.
5. Validate classification and timestamps.

## Validation command set
```bash
curl -sS http://127.0.0.1:8088/api/allstar/inbound-health
curl -sS http://127.0.0.1:8090/api/allstar/inbound/health
curl -sS -X POST -H 'content-type: application/json' -d '{"duration":45}' \
  http://127.0.0.1:8090/api/gmrshub/inbound/test-window
sudo asterisk -rx 'iax2 show registry'
```

## Service reload matrix
- host API changed: `systemctl restart susnet-api`
- module/core code changed: restart only affected containers
- Node-RED flow changed: seed flow file then restart Node-RED container

## Documentation policy
Every non-trivial change must update:
- technical docs (`susnet-next/docs/*`)
- operator docs (`BuildFiles/Human/*`)
- process docs (`BuildFiles/Agents/*`)
- session journals (`Journal/*`)
- troubleshooting status (`Troubleshooting/*`)
