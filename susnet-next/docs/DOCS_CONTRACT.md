# Susnet Docs Contract

## Canonical Model
- private-first technical source in this repo
- public-safe projection in `resevoir-pis`

## Required Per Meaningful Change
1. update affected architecture and contracts docs
2. update `docs/CHANGE_IMPACTS.md` if change class mapping shifts
3. create/update `docs/refactors/<refactor-id>/` bundle
4. include debugging chronology and restabilization outcomes
5. include verification and residual risk summary
6. run `scripts/validate-docs-consistency.sh`

## Hard Rule
Authorization logic must not use channel index; use channel identity (name plus fingerprint) and sender policy.
