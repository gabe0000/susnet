# susnet Owner's Manual

## Canonical State
- Host role: control-plane authority (`Joe Cabot`)
- Agent responsibilities:
  - central policy and ACL decisions
  - orchestration dispatch to edge agents
  - direct web/API interaction path
- Edge counterpart: `Mr. Pink` on MeshBox
- Transport to edge: MQTT over Tailscale
- Action gate model: dedicated channel identity (name + key fingerprint) + allowlist
- RF overflow behavior: compact summary + rephrase prompt (max 5 chunks at edge)
- Canonical architecture docs: https://github.com/gabe0000/resevoir-pis
- Last validated: 2026-02-22
- Validator: `scripts/validate-docs.sh v1`

## Definition of Done
- [ ] Control-plane change applied
- [ ] Verification complete
- [ ] Owner manual updated
- [ ] Journal/logbook/changelog updated
- [ ] Validation script passes
