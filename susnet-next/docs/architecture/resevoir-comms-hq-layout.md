# Resevoir Comms HQ Layout

## Purpose
Define the canonical storage and runtime layout under `/data/Resevoir-Comms-HQ` so Office, Library, and Desk concerns stay explicit and isolated.

## Canonical Root
- `/data/Resevoir-Comms-HQ`

## Required Tree
- `/data/Resevoir-Comms-HQ/Library`
- `/data/Resevoir-Comms-HQ/Library/streams`
- `/data/Resevoir-Comms-HQ/Library/books`
- `/data/Resevoir-Comms-HQ/Library/corpus/active`
- `/data/Resevoir-Comms-HQ/Library/corpus/staging`
- `/data/Resevoir-Comms-HQ/Library/index`
- `/data/Resevoir-Comms-HQ/Library/alerts`
- `/data/Resevoir-Comms-HQ/Offices/Joe`
- `/data/Resevoir-Comms-HQ/Offices/Mr-Pink`
- `/data/Resevoir-Comms-HQ/Desks/Joe`
- `/data/Resevoir-Comms-HQ/Desks/Mr-Pink`
- `/data/Resevoir-Comms-HQ/Models/Ollama`
- `/data/Resevoir-Comms-HQ/Runbooks`
- `/data/Resevoir-Comms-HQ/Stacks`
- `/data/Resevoir-Comms-HQ/Ops`

## Ownership Model
- Canonical host: Susnet.
- Library is shared and canonical on Susnet.
- Office paths are agent-owned.
- Desk paths are per-agent hot context checkpoints.

## Runtime Path Mapping
- Legacy Library root: `/data/Mr-Pinks-Library` -> target `/data/Resevoir-Comms-HQ/Library`
- Legacy Joe Office: `/data/Joes-Office` -> target `/data/Resevoir-Comms-HQ/Offices/Joe`
- Legacy Ollama model path: `/home/codex/ollama` -> target `/data/Resevoir-Comms-HQ/Models/Ollama`

## Cutover Strategy
1. Build new tree and write adapters.
2. Dual-write and parity-check.
3. Atomically switch runtime mounts and env paths.
4. Keep rollback compatibility window before removing legacy paths.
