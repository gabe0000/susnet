# 10 Governance

## Scope
This repository documents Susnet control-plane implementation and operations.

## Authority and Precedence
1. Canonical architecture/governance: `resevoir-pis`
2. This repo's canonical state: `docs/owners-manual/README.md`
3. Detailed narrative: `docs/JOURNAL.md`
4. Summary trail: `docs/LOGBOOK.md` and `docs/CHANGELOG.md`

## Public-Safe Rule
This repo is public-safe documentation and implementation detail.
Sensitive private edge details must remain in `meshbox-privat`.

## Update Contract
For every meaningful change:
1. Update canonical owner-manual state.
2. Update quickstart/ops docs if operator workflow changed.
3. Append journal entry with context/decision/verification.
4. Update logbook/changelog.
5. Run `scripts/validate-docs.sh`.
