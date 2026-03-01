# Office Library Desk Contract

## Purpose
Set the storage and permission boundary contract for all agent runtime components.

## Library
- Scope: shared durable knowledge and telemetry artifacts.
- Canonical path: `/data/Resevoir-Comms-HQ/Library`.
- Contents:
  - raw stream rings
  - normalized books
  - staged and active corpora
  - indexes
  - alert records
- Access default: read-only for agents; write allowed only to designated writer services.

## Office
- Scope: agent-owned state, policy, and permission surface.
- Canonical paths:
  - `/data/Resevoir-Comms-HQ/Offices/Joe`
  - `/data/Resevoir-Comms-HQ/Offices/Mr-Pink`
- Required subpaths:
  - `state`
  - `policy`
  - `permissions`
  - `audit`
  - `expertise`
- Access rule: one owning identity per office, fail closed if ownership is wrong.

## Desk
- Scope: hot context and low-latency working memory.
- Canonical paths:
  - `/data/Resevoir-Comms-HQ/Desks/Joe`
  - `/data/Resevoir-Comms-HQ/Desks/Mr-Pink`
- Storage mode: Redis hotset plus file checkpoints.
- Default window:
  - 2 hours of hot context
  - last 200 conversation turns
  - summarize every 15 minutes

## Isolation Rules
1. Channel index must never be used for authorization.
2. Authorization must use channel identity (name and fingerprint) plus sender policy.
3. Joe may read Mr. Pink expertise outputs but cannot modify Mr. Pink-owned files.

## Validation Expectations
- Startup checks verify path existence, ownership, mode, and mount orientation.
- Violations emit policy events and fail runtime initialization.
