#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

required=(
  docs/DOCS_CONTRACT.md
  docs/CHANGE_IMPACTS.md
  docs/architecture/system-map.md
  docs/architecture/component-boundaries.md
  docs/architecture/permission-gates-matrix.md
  docs/architecture/message-flows.md
  docs/architecture/cross-host-component-map.md
  docs/architecture/surfaces/stock-meshtastic.md
  docs/architecture/surfaces/edge-bridge-mr-pink.md
  docs/architecture/surfaces/control-runtime-joe-openclaw.md
  docs/architecture/surfaces/permission-gates.md
  docs/contracts/stock-meshtastic-mqtt-contract.md
  docs/contracts/custom-meshbox-susnet-agent-contract.md
  docs/refactors/README.md
  docs/refactors/templates/refactor-entry.md
  docs/refactors/templates/restabilization-log.md
)

for f in "${required[@]}"; do
  [[ -f "$f" ]] || { echo "missing: $f"; exit 1; }
done

find docs/refactors -mindepth 1 -maxdepth 1 -type d ! -name templates | while read -r d; do
  for rf in 01-context-and-goals.md 02-design-and-changes.md 03-debugging-and-restabilization.md 04-verification-and-known-risks.md; do
    [[ -f "$d/$rf" ]] || { echo "missing: $d/$rf"; exit 1; }
  done
done

grep -qi "private-first" docs/DOCS_CONTRACT.md || { echo "missing private-first rule"; exit 1; }
grep -q "must never be used for authorization" docs/architecture/surfaces/permission-gates.md || { echo "missing channel-index anti-pattern"; exit 1; }

echo "validate-docs-consistency.sh: OK"
