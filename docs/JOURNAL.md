# JOURNAL

## RP-20260222-001 (linked)
- Date/Time: 2026-02-22 07:30 EST
- Context: Wave 1 documentation alignment for susnet as control-plane authority.
- Decision: Add layered docs contract aligned to canonical `resevoir-pis`.
- Implementation:
  - Added docs contract, owner manual canonical state, governance section.
  - Linked to canonical architecture repo and event id.
  - Declared public-safe docs policy in susnet.
- Failure(s) / Incident(s): None.
- Verification:
  - `scripts/validate-docs.sh` passes.
- Open Risks / Follow-ups:
  - Host-level runtime alignment work is deferred to Wave 2.

## RP-20260227-001 (linked)
- Date/Time: 2026-02-27 09:10 EST
- Context: Documentation governance expansion across Susnet, MeshBox, and public `resevoir-pis`.
- Decision: Adopt private-first canonical docs with sanitized public projection and explicit permission-gate contracts.
- Implementation:
  - Added architecture system map, boundaries, permission gates matrix, and message flows.
  - Added stock Meshtastic and custom agent contract split.
  - Added change impact matrix and consistency validation script.
- Failure(s) / Incident(s): None.
- Verification:
  - `scripts/validate-docs.sh` passes on updated docs tree.
- Open Risks / Follow-ups:
  - Keep weekly drift checks active between private and public repos.
