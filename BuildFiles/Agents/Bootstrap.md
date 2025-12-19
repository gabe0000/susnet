# Agent Bootstrap Checklist

Fast onboarding for new agents working on SusNet (private repo). Keep this minimal, read `AgentOps.md` for deeper rules.

1) **Verify remotes**  
   - `git remote -v` should point to `https://github.com/gabe0000/susnet.git` (private).  
   - Do not add new remotes without approval.

2) **Check working tree**  
   - `git status --short` and scan for untracked piles (venv, logs, binaries, backups). Leave them alone unless told otherwise.  
   - If you need to ignore noise, propose a `.gitignore` update; do not delete artifacts.

3) **Context first**  
   - Read latest Journal entries and open Troubleshooting tickets.  
   - Review `BuildFiles/Agents/AgentOps.md` and `BuildFiles/Human/*` so you match the expected flow.

4) **Doc vs code handling**  
   - Repo is private; still treat secrets with care. Do not push credentials, venvs, logs, or firmware blobs.  
   - When preparing doc-only updates for public sharing, stage only docs (README, BuildFiles, Troubleshooting, Journal). Keep code changes local unless explicitly approved to push.

5) **Safe ops**  
   - Avoid destructive commands (`rm -rf`, resets) unless explicitly requested.  
   - Service restarts: use `/home/gabe0000/restart_susnet.sh` when changes need a refresh (local only).  
   - Prefer light validation (`python -m py_compile file.py`, lint/html spot checks) over heavy test runs unless needed.

6) **Meshtastic/channel hygiene**  
   - Map channels by name/hash, not slot index. If names are missing, fetch/derive channel data before rendering UI.  
   - Display node long names wherever possible; IDs only as a fallback.

7) **Logging your work**  
   - Note actions and outcomes in Journal and relevant ticket files.  
   - If you cannot finish, leave clear next steps.

8) **Before pushing**  
   - Re-check `git status`, confirm only intended files are staged.  
   - Summarize in commit message what changed and why.  
   - Push to `master` after validation and journaling.
