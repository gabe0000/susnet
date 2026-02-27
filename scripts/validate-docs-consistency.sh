#!/usr/bin/env bash
set -euo pipefail

required=(
  docs/architecture/system-map.md
  docs/architecture/component-boundaries.md
  docs/architecture/permission-gates-matrix.md
  docs/architecture/message-flows.md
  docs/contracts/stock-meshtastic-mqtt-contract.md
  docs/contracts/custom-meshbox-susnet-agent-contract.md
  docs/CHANGE_IMPACTS.md
)

for f in "${required[@]}"; do
  [[ -f "$f" ]] || { echo "missing: $f"; exit 1; }
done

grep -q "Permission Gates Matrix" docs/architecture/system-map.md || { echo "system-map missing gate link"; exit 1; }
grep -q "msh/US" docs/contracts/stock-meshtastic-mqtt-contract.md || { echo "stock contract missing topic root"; exit 1; }
grep -q "susnet/agent/query" docs/contracts/custom-meshbox-susnet-agent-contract.md || { echo "custom contract missing query topic"; exit 1; }
grep -q "Definition of Done" docs/CHANGE_IMPACTS.md || { echo "change impacts missing DoD rule"; exit 1; }

echo "validate-docs-consistency.sh: OK"
