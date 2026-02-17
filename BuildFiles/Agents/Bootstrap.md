# Agent Bootstrap Checklist

## Mission rules
- Keep RF/voice path stable first.
- Prefer additive changes over rewrites.
- Back up before host config edits.
- Never publish secrets.

## Start-of-session workflow
1. Read latest Journal entries and `Troubleshooting/master.md`.
2. Check local git status and dirty tree scope.
3. Verify runtime health:
   - `systemctl is-active asterisk susnet-api`
   - `sudo docker ps`
4. Confirm gateway health:
   - `curl -sS http://127.0.0.1:8090/api/health`

## Inbound diagnostics workflow
1. Collect baseline:
   - `/home/gabe0000/susnet-next/scripts/collect_inbound_baseline.sh`
2. Query health endpoints:
   - `/api/allstar/inbound/health`
   - `/api/gmrshub/inbound/health`
3. Run 45s test windows where needed.
4. Classify via L1/L2/L3/L4 taxonomy.

## Safe deployment workflow
1. Edit repo copy first (`/home/gabe0000/...`).
2. Validate syntax.
3. Deploy to live path (`/opt/susnet-api`) only after validation.
4. Restart only touched services.
5. Re-check health and endpoint output.

## End-of-session workflow
1. Update docs/manuals/playbooks impacted by changes.
2. Add detailed journal entries with commands/results.
3. Build NotesLM package for long-form recap.
4. Run secret scan before staging commits.
