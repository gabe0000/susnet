# 01 Context and Goals

## Phase A: Baseline (Before)
- Runtime was semi-stable with active edge/control flow and documented intermittent quality issues.
- Existing storage roots existed as separate legacy paths:
  - `/data/Mr-Pinks-Library`
  - `/data/Joes-Office`
- Protobuf stream and books existed but governance was not unified under a single building root.
- Model storage was on `/home/codex/ollama`, outside the planned canonical HQ structure.

## Problem Statement
The project needed one canonical storage and governance model that aligns runtime operations, permissions, and documentation.

## Goals
1. Formalize Office, Library, and Desk under `/data/Resevoir-Comms-HQ`.
2. Document containerization boundaries and storage governance clearly.
3. Introduce allowlist-gated `become_an_expert` workflow contract.
4. Keep stock Meshtastic and `susnet/agent/*` wire contracts stable.
5. Keep documentation synchronized across private and public repos.
