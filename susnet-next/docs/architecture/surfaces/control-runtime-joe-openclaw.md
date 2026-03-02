# Surface: Control Runtime (Joe/OpenClaw)

## Scope
Control-host runtime that processes `susnet/agent/query` and emits lifecycle responses while preserving contract shape under multiple execution modes.

## Responsibilities
- validate query envelope and required identity/context fields
- emit lifecycle (`ack/progress/reply/error/dlq`) with stable correlation
- execute primary response path through local runtime/model
- optionally escalate to OpenClaw/tool path when enabled and policy allows
- preserve deterministic terminal behavior (single terminal path per request)

## Primary Components
- `custom-agent-gateway` service
- Redis-backed request/session state
- local model runtime path
- optional OpenClaw execution surface

## Current Runtime Posture
1. Baseline operation favors stable edge conversation flow over deep tool execution.
2. OpenClaw escalation is treated as optional and can be degraded/disabled without breaking base contract behavior.
3. Fallback behavior must remain explicit, bounded, and observable.

## Control-Plane Invariants
- contract topics and envelope shape remain backward compatible for edge consumers
- no authorization decision uses channel index values
- retries/timeouts must converge to a deterministic terminal outcome
