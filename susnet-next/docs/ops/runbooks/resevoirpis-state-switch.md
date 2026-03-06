# ResevoirPis State Switch (Private Canonical)

## Scope
Operational state switch between `normal` and `resevoir` host posture using the `ResevoirPis` command surface.

## Controlled Services
Managed set and protected set are sourced from:
- `ops/resevoir-stack/shutdown-targets.txt`
- `ops/resevoir-stack/protected-services.txt`

## Core Guarantees
1. Snapshot on every transition (`up` and `down`).
2. Protected services are never controlled by transition logic.
3. Tailscale is preflight-only and out of lifecycle scope.
4. Restore failure triggers rollback attempt to pre-transition bundle.

## Snapshot Bundle
Bundles are written under `~/resevoirpis-state-bundles/<state>/<timestamp>/` and include:
- `manifest.json`
- status captures
- allowlisted file bundle
- managed volume backups
- `SHA256SUMS.txt`

## Notes
This is private canonical runtime guidance; public projection is maintained in `resevoir-pis/docs/runbooks/resevoirpis-operations.md`.
