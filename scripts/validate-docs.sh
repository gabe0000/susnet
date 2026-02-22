#!/usr/bin/env bash
set -euo pipefail
required=(
  docs/JOURNAL.md
  docs/LOGBOOK.md
  docs/CHANGELOG.md
  docs/DOCS_CONTRACT.md
  docs/owners-manual/README.md
  docs/owners-manual/10-governance.md
)
for f in "${required[@]}"; do
  [[ -f "$f" ]] || { echo "missing: $f"; exit 1; }
done

grep -q "resevoir-pis" docs/DOCS_CONTRACT.md || { echo "missing canonical link"; exit 1; }
grep -q "public-safe" docs/DOCS_CONTRACT.md || { echo "missing sensitivity rule"; exit 1; }
echo "validate-docs.sh: OK"
