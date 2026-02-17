# 2026-02-17 Session: Inbound Hardening (Planning + Execution)

## Planning Context
Objective: implement local-only inbound stabilization for AllStar/GMRSHub without disturbing live RF operations.
Constraints:
- no cloud relay
- no destructive resets
- host Asterisk remains production
- containerize control plane where possible

## Baseline Before Changes
- Created rollback bundles:
  - `/home/gabe0000/backups/inbound-hardening-20260216-222812/`
  - `/home/gabe0000/backups/susnet-pre-inbound-hardening-20260216-222812.tgz`
- Captured:
  - `iax2 show registry`
  - `iax2 show peers`
  - UDP listeners
  - firewall snapshots
  - extnodes tar snapshots
- Verified root cron only has single GMRS updater entry.

## Execution Steps
1. Synced live host API file from `/opt/susnet-api/susnet_api.py` into repo copy to avoid divergence.
2. Added inbound diagnostics helpers in host API:
   - public IP detection
   - registry parser
   - UDP 4569 listener detection
   - state persistence under troubleshooting tree
   - test-window packet capture logic with safe fallback when `tcpdump` missing
3. Added host routes:
   - `GET /api/allstar/inbound-health`
   - `POST /api/allstar/inbound-test-window`
   - `GET /api/gmrshub/inbound-health`
   - `POST /api/gmrshub/inbound-test-window`
4. Added V2 module proxy routes:
   - module-allstar `/inbound/health`, `/inbound/test-window`
   - module-gmrshub `/inbound/health`, `/inbound/test-window`
5. Added gateway routes:
   - `/api/allstar/inbound/health`
   - `/api/allstar/inbound/test-window`
   - `/api/gmrshub/inbound/health`
   - `/api/gmrshub/inbound/test-window`
6. Updated Node-RED v2 flow pack:
   - AllStar inbound readiness text block
   - GMRS inbound readiness text block
   - AllStar/GMRS manual 45s test-window buttons and result blocks
7. Applied low-risk `iax.conf` hardening (post-backup):
   - explicit bind address
   - registration expiry controls (`defaultexpire`, `minregexpire`, `maxregexpire`)
8. Restarted only changed services/containers:
   - `susnet-api`
   - `susnet-module-allstar`
   - `susnet-module-gmrshub`
   - `susnet-core-api`
   - `susnet-next-nodered`
9. Seeded updated Node-RED flow file via direct flow copy script and restarted Node-RED.

## Validation Results
- Host API health: `ok=true`.
- New host inbound health endpoints return expected schema.
- New gateway inbound health endpoints return expected schema.
- Test-window endpoints execute and return deterministic result.
- Current environment reports `tcpdump not installed`; test-window returns `ok=false` with explicit `stderr` (expected behavior for now).
- `iax2 show registry` returned registered states after reload/restart.

## Risk/Regression Notes
- `susnet-api` restart can hang on shutdown because of long-lived connections; used controlled stop/start path.
- No RF tuning stanza changes were applied in `rpt.conf` in this cycle.
- Diagnostics are classify-only and do not auto-remediate.

## Next Actions
1. Install `tcpdump` if packet-capture test-window is required.
2. Validate inbound from a known external peer while test-window is running.
3. Add explicit operator guidance for L1 vs L2 discrimination with external observer node.
4. Continue module-native migration while keeping host RF stable.
