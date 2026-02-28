# Verification And Known Risks

Verification:
- core-api update deployed and syntax-checked
- susnet-core-api container restarted cleanly
- Node-RED restarted with updated poll intervals and returned healthy
- docs consistency validator passes

Measured runtime signal:
- module-meshtastic request rate from core-api reduced about 50% on key polled endpoints in 2-minute sampling window
- post-change container CPU sample remained low for:
  - susnet-module-meshtastic
  - susnet-core-api
  - susnet-next-nodered

Known risks:
- event-driven replacement for polling remains pending
- dashboard freshness is slightly reduced due safer poll intervals
- broader runtime branch still contains unrelated in-progress changes; keep commits path-scoped

Additional verification (second runtime pass):
- meshtastic module patched and syntax-validated (`python -m py_compile`)
- module restarted and resumed API responses
- during ~2 minute post-patch sampling, meshtastic CPU stayed low (typically sub-1%, brief low single-digit peaks)
- `nodes.json` mtime remained stable during repeated dashboard polls, confirming write-churn removal

Additional known risk:
- current container spec is brittle when a fixed serial by-id device path disappears between restarts; prefer resilient device strategy in compose/runtime config.
