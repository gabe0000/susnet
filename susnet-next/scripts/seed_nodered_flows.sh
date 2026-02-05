#!/usr/bin/env bash
set -euo pipefail

FLOW_FILE_DEFAULT="/home/gabe0000/susnet-next/services/node-red/flows/susnet_flows_v2.json"
FLOW_FILE="${1:-$FLOW_FILE_DEFAULT}"
SECRETS_FILE="/home/gabe0000/susnet-next/.secrets/initial_credentials.txt"
NODERED_URL="http://127.0.0.1:1881"

if [[ ! -f "$FLOW_FILE" ]]; then
  echo "missing flow file: $FLOW_FILE" >&2
  exit 1
fi

NR_USER=$(awk -F': ' '/^Node-RED user:/ {print $2}' "$SECRETS_FILE")
NR_PASS=$(awk -F': ' '/^Node-RED password:/ {print $2}' "$SECRETS_FILE")

if [[ -z "${NR_USER:-}" || -z "${NR_PASS:-}" ]]; then
  echo "Node-RED credentials not found in $SECRETS_FILE" >&2
  exit 1
fi

TOKEN=$(curl -sS -X POST "$NODERED_URL/auth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=node-red-admin' \
  --data-urlencode 'scope=*' \
  --data-urlencode "username=$NR_USER" \
  --data-urlencode "password=$NR_PASS" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))')

if [[ -z "$TOKEN" ]]; then
  echo "failed to authenticate to Node-RED" >&2
  exit 1
fi

HTTP=$(curl -sS -o /tmp/nodered_seed_resp.json -w '%{http_code}' \
  -X POST "$NODERED_URL/flows" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @"$FLOW_FILE")

echo "HTTP:$HTTP"
cat /tmp/nodered_seed_resp.json

if [[ "$HTTP" != "204" && "$HTTP" != "200" ]]; then
  exit 1
fi

echo "Node-RED flows seeded."
