# Docs Contract (susnet)

## Scope
This repo documents Susnet control-plane implementation and operations under a private-first documentation model.

## Canonical Model
- Private-first source of truth: `susnet` and `meshbox-privat` technical docs.
- Public projection: sanitized architecture/contracts in `resevoir-pis`.

## Update Requirements
1. Update `docs/owners-manual/README.md` canonical state for control-plane changes.
2. Update affected architecture and contract docs.
3. Update `docs/CHANGE_IMPACTS.md` for new change classes.
4. Append detailed `docs/JOURNAL.md` entry referencing canonical ID.
5. Add concise `docs/LOGBOOK.md` and `docs/CHANGELOG.md` entries as applicable.
6. Run `scripts/validate-docs.sh`.

## Canonical Authority
- Public architecture reference: https://github.com/gabe0000/resevoir-pis
- Control-plane implementation: https://github.com/gabe0000/susnet

## Sensitivity Rule
- Public-safe docs only are exported to the public repo.
- Secrets, private addresses, and credentials must never be published.
