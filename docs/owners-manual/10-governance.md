# 10 Governance

## Role Boundaries
- susnet (`Joe Cabot`): central authority, policy decisions, orchestration.
- meshbox (`Mr. Pink`): RF ingestion/execution edge under policy gates.

## Documentation Precedence
1. `resevoir-pis` canonical architecture and contracts
2. `susnet` control-plane docs
3. `meshbox-privat` edge private docs
4. Journal/logbook/changelog summaries

## Public-safe Requirement
Do not commit secrets, private keys, exact device IDs, or private network topology here.

## Cross-Repo Journal Link Rule
Operationally significant susnet entries should include canonical event IDs (e.g., `RP-YYYYMMDD-###`).
