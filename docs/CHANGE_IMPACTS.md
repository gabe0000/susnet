# Change Impacts Matrix (Susnet)

| Change Type | Required Docs |
| --- | --- |
| Broker user/ACL update | `docs/architecture/permission-gates-matrix.md`, `docs/contracts/*.md`, `docs/JOURNAL.md` |
| Topic name/prefix update | `docs/contracts/*.md`, `docs/architecture/message-flows.md`, `docs/CHANGELOG.md` |
| Identity or permission gate update | `docs/architecture/permission-gates-matrix.md`, `docs/owners-manual/README.md`, `docs/JOURNAL.md` |
| Service boundary/ownership change | `docs/architecture/system-map.md`, `docs/architecture/component-boundaries.md`, `docs/LOGBOOK.md` |
| Validation gate change | `scripts/validate-docs.sh`, `scripts/validate-docs-consistency.sh`, `docs/DOCS_CONTRACT.md` |

## Definition of Done Rule
If a change row applies, listed docs must be updated in the same change set before completion.
