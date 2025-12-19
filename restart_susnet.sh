#!/usr/bin/env bash
# Restart all SusNet services (local only).
# Services covered: susnet-api, meshtastic-listener, meshtastic-aprs, dvswitch_mode_switcher, asterisk.

set -euo pipefail

SERVICES=(
  "susnet-api.service"
  "meshtastic-listener.service"
  "aprs-listener.service"
  "dvswitch_mode_switcher.service"
  "asterisk.service"
)

echo "Restarting SusNet services..."
for svc in "${SERVICES[@]}"; do
  echo "-> $svc"
  sudo systemctl restart "$svc"
done

echo "Checking status..."
for svc in "${SERVICES[@]}"; do
  systemctl is-active --quiet "$svc" && status="active" || status="inactive"
  printf "%-30s %s\n" "$svc" "$status"
done

echo "Done."
