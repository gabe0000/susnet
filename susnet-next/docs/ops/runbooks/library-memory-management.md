# Library Memory Management Runbook

## Audience
Operator or external high-compute assistant managing local library capacity and stability.

## Scope
- Canonical target: `/data/Resevoir-Comms-HQ/Library`.
- Use this runbook when threshold or cap alerts are emitted.

## Required Inputs
1. Current used space and growth trend.
2. Last threshold crossed.
3. Current ingest status (active, paused, failed).
4. Recent policy events for ingest and cap manager.

## Safe Cleanup Order
1. Verify cap-triggered ingest pause is active.
2. Snapshot current index and corpus metadata.
3. Identify least recent expert domains by access and update time.
4. Remove stale staged corpora first.
5. Remove inactive expert overlays second.
6. Rebuild index metadata.
7. Re-run contract and docs consistency validators.
8. Resume ingest only after validation passes.

## Validation Checklist
- Active corpus pointers resolve.
- Index scan returns no broken references.
- Policy events confirm ingest resumed.
- No cross-office ownership violations.

## Do Not Do
- Do not remove active corpus without replacement.
- Do not bypass allowlist gate logic.
- Do not publish credentials or host access details in documentation artifacts.

## Escalation
If cleanup cannot restore headroom, raise an operator incident and keep ingest paused.
