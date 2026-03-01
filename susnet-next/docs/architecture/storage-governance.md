# Storage Governance

## Canonical Scope
- Managed tree: `/data/Resevoir-Comms-HQ`.
- Governed focus: `Library`, `Offices`, `Desks`, and `Models`.

## Library Capacity Policy
- Total Library cap: 20GB.
- Raw protobuf ring budget: 100MB.
- Threshold checkpoints by used space:
  - 5GB
  - 10GB
  - 15GB
  - every additional 500MB after 15GB

## Threshold Signals
At each threshold crossing:
1. Send human-readable Joe alert on the dedicated channel.
2. Emit structured policy event on MQTT.
3. Record checkpoint event in Library alerts.

## Overflow Behavior
- At Library cap, pause new expert corpus ingestion.
- Continue normal request lifecycle and relay behavior.
- Emit repeated cap-state alerts until acknowledged and resolved.
- Recovery path is runbook-driven cleanup and revalidation.

## Retention and Pruning
- Raw stream is ring-managed and self-bounded.
- Books and indices prune oldest low-priority artifacts only during operator-approved cleanup.
- Corpus promotion keeps active and previous snapshots for rollback safety.

## Runbook
- External memory-management bootstrap guide: `docs/ops/runbooks/library-memory-management.md`.
