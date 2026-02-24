# CHANGELOG

## 2026-02-22
- Added full docs system on `master`: owner manual, governance, quickstart, journal, logbook, and docs contract.
- Documented current Susnet control-plane runtime state and direct SSH terminal query workflow.
- Recorded storage partition expansion and `/data` activation details.

## 2026-02-22
- Extended Joe Cabot query handling for conversational prompts beyond fixed summary intents.
- Added local-model best-effort chat path with bounded fallback replies for reliability.
- Kept action scope in safe lightweight mode and RF-size output limits.

## 2026-02-22
- Added one-command direct CLI for Joe Cabot over MQTT (`joe`, `ask-joe`) with chat mode and retry defaults.

## 2026-02-24
- Added front-desk control lifecycle alignment with MeshBox: `ack`, `progress`, `control`, `error`, and `dlq` topics.
- Documented deterministic timeout semantics used by Mr Pink escalations: unreachable vs busy timeout classification.
- Synced owner manual to current control-plane contract and timing defaults.

## 2026-02-24
- Added arithmetic reliability guardrail in Joe runtime for simple numeric expressions.
- Added query sanitization to strip bridge RF constraint metadata before intent/math handling.
- Set local model temperature to `0.0` to reduce stochastic drift in short deterministic answers.

## 2026-02-24
- Added tracked Joe runtime source tree at `susnet-next/services/joe-cabot-lite/`.
- Added `scripts/deploy-joe-cabot-lite.sh` to sync tracked source into `/home/codex/joe-cabot-lite` with compile and service restart checks.
- Closed runtime provenance gap by documenting source-of-truth and deploy path in owner manual and quickstart.
