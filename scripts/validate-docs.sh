#!/usr/bin/env bash
set -euo pipefail
required=(
  docs/JOURNAL.md
  docs/LOGBOOK.md
  docs/CHANGELOG.md
  docs/DOCS_CONTRACT.md
  docs/owners-manual/README.md
  docs/owners-manual/10-governance.md
  docs/architecture/system-map.md
  docs/architecture/component-boundaries.md
  docs/architecture/permission-gates-matrix.md
  docs/architecture/message-flows.md
  docs/contracts/stock-meshtastic-mqtt-contract.md
  docs/contracts/custom-meshbox-susnet-agent-contract.md
  docs/CHANGE_IMPACTS.md
  scripts/validate-docs-consistency.sh
)
for f in "${required[@]}"; do
  [[ -f "$f" ]] || { echo "missing: $f"; exit 1; }
done

grep -qi "private-first" docs/DOCS_CONTRACT.md || { echo "missing canonical model"; exit 1; }
grep -qi "public-safe" docs/DOCS_CONTRACT.md || { echo "missing sensitivity rule"; exit 1; }
./scripts/validate-docs-consistency.sh

echo "validate-docs.sh: OK"
