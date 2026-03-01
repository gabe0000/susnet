# Become An Expert Contract

## Purpose
Define the allowlisted workflow that lets an agent ingest and maintain an expertise corpus on demand and on schedule.

## Gate Rules
1. Invocation intent: `become_an_expert`.
2. Caller must be on allowlist.
3. Unauthorized callers are denied with audited policy events.

## Interactive Flow
1. Prompt A:
- `Which agent needs to become an expert?`
2. Prompt B (repeat loop):
- `Paste a resource link here or type end if you are finished.`
3. Continue collecting links until user sends `end`.
4. On `end`, begin staged ingest.

## Accepted Sources
- Web documentation links.
- Git repository links.
- Documentation file links.

## Storage Contract
- Budget: 500MB per agent per expertise domain.
- Shared parsed base corpus lives in Library.
- Agent-specific overlays, notes, and permissions live in agent Office expertise path.

## Refresh Contract
- On-demand refresh is allowed for allowlisted callers.
- Cooldown: 15 minutes per agent per expertise domain.
- Scheduled refresh: weekly Sunday at 04:00 EST.
- Activation mode: stage then promote.

## Failure Contract
- If staging or validation fails, keep active corpus unchanged.
- Emit `expert_ingest_failed` with failure reason.
- If Library cap is reached, pause ingest and emit cap alerts.

## Event Contract
- `expert_ingest_started`
- `expert_ingest_staged`
- `expert_ingest_promoted`
- `expert_ingest_failed`
- `library_threshold_crossed`
- `library_cap_reached_paused`
- `library_ingest_resumed`
