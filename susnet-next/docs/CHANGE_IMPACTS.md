# Change Impacts

## Rule
Every infra/config/auth/topic change must include matching docs updates in this repo and a public-safe projection update in `resevoir-pis` when allowed.

## Mapping
| Change Type | Required Private Docs |
| --- | --- |
| service runtime/container changes | `docs/architecture/*`, `docs/refactors/*`, `docs/CHANGE_IMPACTS.md` |
| auth/ACL/policy changes | `docs/architecture/permission-gates-matrix.md`, `docs/contracts/*`, refactor bundle |
| topic/schema changes | `docs/contracts/*`, `docs/architecture/message-flows.md`, refactor bundle |
| storage/layout changes | `docs/architecture/resevoir-comms-hq-layout.md`, `docs/architecture/storage-governance.md`, refactor bundle |
| expert corpus workflow changes | `docs/contracts/become-an-expert-contract.md`, `docs/ops/runbooks/library-memory-management.md`, refactor bundle |
| stabilization/debug cycles | `docs/refactors/*/03-debugging-and-restabilization.md` |
