#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${1:-/home/gabe0000/backups/inbound-checks-${TS}}"
mkdir -p "$OUT_DIR"

run_cmd() {
  local name="$1"
  shift
  {
    echo "# cmd: $*"
    echo "# ts: $(date -Is)"
    "$@"
  } >"${OUT_DIR}/${name}.txt" 2>&1 || true
}

run_cmd iax2_show_registry /usr/sbin/asterisk -rx 'iax2 show registry'
run_cmd iax2_show_peers /usr/sbin/asterisk -rx 'iax2 show peers'
run_cmd ss_udp_4569 /usr/bin/ss -lunp
run_cmd ip_addr /usr/sbin/ip -br a
run_cmd gmrs_extnodes_head /usr/bin/head -n 40 /var/lib/asterisk/rpt_extnodes_gmrs
run_cmd allstar_extnodes_head /usr/bin/head -n 40 /var/lib/asterisk/rpt_extnodes

PUBLIC_IP=""
for URL in https://api.ipify.org https://ifconfig.me/ip; do
  if PUBLIC_IP="$(/usr/bin/curl -fsSL --max-time 4 "$URL" 2>/dev/null)"; then
    [[ "$PUBLIC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && break
  fi
  PUBLIC_IP=""
done

cat > "${OUT_DIR}/summary.json" <<JSON
{
  "timestamp": "$(date -Is)",
  "out_dir": "${OUT_DIR}",
  "public_ip": "${PUBLIC_IP}",
  "failure_taxonomy": [
    "L1 ISP/CGNAT blocked",
    "L2 Router NAT/forward mismatch",
    "L3 Host firewall/socket issue",
    "L4 Asterisk auth/context/codec reject"
  ]
}
JSON

echo "${OUT_DIR}"
