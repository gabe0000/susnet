# Agent Ops Guide

Quick-start and safeguards for coding agents working on SusNet. Default: local repo may hold code; GitHub remote is **docs-only**.

## Daily checklist
- Read context: current tasks, open tabs, and latest Journal entry.
- `git status --short` per repo; do not disturb unrelated/untracked piles (venv, caches, personal files).
- Validate changes lightly: `python -m py_compile <file>`, open HTML locally, avoid heavy/destructive commands by default.
- If services must be refreshed, use `/home/gabe0000/restart_susnet.sh` (local only). Do not publish this script.
- Keep queue/log files intact; never delete user data unless asked.

## Channel/hash specifics (Meshtastic)
- Channel selection is by **hash** (name + PSK), not slot number. Always resolve channel by name against the local channel table; avoid hard-coding indexes.
- If names are missing, fetch channels via `node.requestChannels()`/`waitForConfig` before mapping name → index.

## Doc-only publishing rules
- GitHub remote (`origin` → https://github.com/gabe0000/susnet) is documentation-only. Do not push code, logs, binaries, venvs, or secrets there.
- Before pushing docs: stage only doc files; `git status --short` must show only docs staged/committed.
- Keep local commits for code as needed; only push docs upstream.

## When stuck
- Log what you tried, what failed, and suggested next steps in Journal and/or BuildFiles.
- Ask before destructive actions; never wipe or reset user changes.
