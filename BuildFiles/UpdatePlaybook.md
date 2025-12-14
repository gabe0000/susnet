# Update Playbook (Docs-Only)

Use this when asked to “update everything” and keep GitHub limited to documentation only. No code, secrets, or private data should be published. Local repo can hold everything; the GitHub repo (`origin` → https://github.com/gabe0000/susnet) must stay docs-only.

## What “update everything” means
- Verify local changes are complete and tested.
- Align working trees so nothing gets lost or overwritten.
- Publish **documentation only** to GitHub (no source code, no credentials).

## Runbook
1. **Collect context**
   - List top-level repos/directories you touched (e.g., `meshtastic`, `private-ui`, `BuildFiles`).
   - Note which files changed (use `git status` and `git diff` per repo).
2. **Stabilize local state**
   - Do **not** undo user changes. Avoid destructive commands (`git reset --hard`, `checkout --`).
   - If there are unrelated changes, leave them untouched.
3. **Validate changes**
   - Run lightweight checks only: for Python, `python -m py_compile <file>`; for web assets, open HTML locally and ensure it loads.
   - If a service needs a restart, record the command but do not run it without explicit approval.
4. **Prepare publishable notes**
   - Summarize what changed, why, and where (paths only; no code).
   - Confirm nothing sensitive is included (no logs, secrets, or IDs beyond public nodes).
   - Keep references to commands minimal and non-destructive (e.g., `git status`, `git diff`).
5. **GitHub step (docs only)**
   - Stage and commit **only** documentation files (e.g., files under `BuildFiles/`, README updates).
   - Before pushing: `git status --short` to confirm only doc files are staged/committed.
   - If the working tree has other changes, stash only the tracked ones you need for the pull: `git stash push -m "temp-rebase" <paths>`; do **not** stash huge untracked trees (venv, caches).
   - `git pull --rebase --autostash origin master` if needed, then `git push origin master`.
6. **Close-out**
   - Leave a brief local note (in `BuildFiles` or Journal) about what was published and any pending work.
   - If something could not be done, document blockers and next actions.

## Guardrails for coding agents
- Never publish code or secrets when the request is “documentation only.”
- Prefer read-only inspection commands unless explicitly approved to modify or restart services.
- Keep changes scoped to the files discussed in the session; do not roam.
- Document assumptions; ask before making irreversible changes.
- Public pushes are **documentation only**: no code, no logs, no credentials, no binaries, no venv/caches. Double-check staged files before pushing.
