# Docs Contract (susnet)

## Scope
This repo documents susnet control-plane implementation and operations in a public-safe format.

## Update Requirements
1. Update `docs/owners-manual/README.md` canonical state for control-plane changes.
2. Update affected topical docs.
3. Append detailed `docs/JOURNAL.md` entry referencing canonical ID.
4. Add concise `docs/LOGBOOK.md` and `docs/CHANGELOG.md` entries as applicable.
5. Run `scripts/validate-docs.sh`.

## Canonical Authority
- Architecture source of truth: https://github.com/gabe0000/resevoir-pis
- Canonical event id used in this wave: `RP-20260222-001`

## Sensitivity Rule
- Public-safe docs only.
- Sensitive edge details belong in private `meshbox-privat` docs.
