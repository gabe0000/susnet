# 03 Debugging and Restabilization

## Phase C: Stabilization

### Observed Risk Areas During Baseline
1. Quality drift between chat and function response voice.
2. Timeout and fallback behavior requiring clearer observability.
3. Documentation drift risk across private and public repos.

### Stabilization Controls Added in This Wave
1. Curated monitoring stream contract documented for high-signal operations.
2. Explicit storage cap behavior documented to avoid uncontrolled ingest churn.
3. Clear runbook for external memory management to reduce recovery ambiguity.
4. Explicit anti-pattern rule retained: channel index never for authorization.

### Remaining Operational Watchpoints
1. Corpus growth under repeated expert ingests.
2. Cooldown effectiveness for on-demand expert refresh.
3. Consistency between private canonical docs and public projection.
