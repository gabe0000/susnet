#!/usr/bin/env bash
set -euo pipefail
required=(
  docs/JOURNAL.md
  docs/LOGBOOK.md
  docs/CHANGELOG.md
  docs/DOCS_CONTRACT.md
  docs/QUICKSTART.md
  docs/owners-manual/README.md
  docs/owners-manual/10-governance.md
)
for f in "${required[@]}"; do
  [[ -f "$f" ]] || { echo "missing: $f"; exit 1; }
done

grep -qi "resevoir-pis" docs/DOCS_CONTRACT.md || { echo "missing canonical link"; exit 1; }
grep -qi "public-safe" docs/DOCS_CONTRACT.md || { echo "missing sensitivity rule"; exit 1; }
grep -q "susnet/agent/query" docs/owners-manual/README.md || { echo "missing query topic in canonical state"; exit 1; }
grep -q "/data" docs/owners-manual/README.md || { echo "missing /data layout in canonical state"; exit 1; }
echo "validate-docs.sh: OK"
