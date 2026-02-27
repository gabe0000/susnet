# susnet Owner's Manual

## Canonical State
- Host role: control-plane authority (`Joe Cabot`).
- Agent responsibilities:
  - central policy and ACL decisions
  - orchestration dispatch to edge agents
  - direct web/API interaction path
- Edge counterpart: `Mr. Pink` on MeshBox.
- Transport to edge: MQTT over private tailnet.
- Action gate model: dedicated channel identity (name + key fingerprint) plus allowlist.
- Contract split:
  - stock path: strict `msh/US/...` Meshtastic semantics
  - custom path: JSON envelope on `susnet/agent/*`
- Canonical architecture docs: https://github.com/gabe0000/resevoir-pis
- Architecture index:
  - `docs/architecture/system-map.md`
  - `docs/architecture/component-boundaries.md`
  - `docs/architecture/permission-gates-matrix.md`
  - `docs/architecture/message-flows.md`
- Last validated: 2026-02-27
- Validator: `scripts/validate-docs.sh v2`

## Definition of Done
- [ ] Control-plane change applied
- [ ] Verification complete
- [ ] Architecture/contracts updated
- [ ] Journal/logbook/changelog updated
- [ ] Validation scripts pass
