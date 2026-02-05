#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/gabe0000/susnet-next"
STACK_DIR="$ROOT/ops/stacks"

mkdir -p \
  "$ROOT/data/portainer" \
  "$ROOT/data/nodered" \
  "$ROOT/data/postgres" \
  "$ROOT/data/mosquitto/data" \
  "$ROOT/data/mosquitto/log"

if [[ ! -f "$STACK_DIR/.env" ]]; then
  cp "$STACK_DIR/.env.example" "$STACK_DIR/.env"
  echo "Created $STACK_DIR/.env from template."
fi

echo "Initialized susnet-next data directories."
echo "Next: edit $STACK_DIR/.env, then run:"
echo "docker-compose -f $STACK_DIR/susnet-next.compose.yml up -d"
