# Update Playbook

## When user says "update everything"
Perform the full cycle:
1. Backups and baseline capture
2. Code/config implementation
3. Targeted service/container reload
4. Validation evidence capture
5. Docs/manual/journal refresh
6. NotesLM export generation
7. Secret scan + git hygiene

## Hard checks before declaring done
- `susnet-api` active
- core gateway health is `ok`
- inbound endpoints return valid schema
- no unrelated services were broken
- docs and journals updated

## Docs-only public rule
If request is explicitly docs-only for public destination:
- publish only markdown/process docs
- exclude code/config/logs/secrets/binaries

## Private repo rule
For private `susnet` repo operations:
- code + docs may be committed
- still never include secret values

## Post-change restart pattern
```bash
sudo systemctl restart susnet-api
sudo docker restart susnet-module-allstar susnet-module-gmrshub susnet-core-api
sudo docker restart susnet-next-nodered
```
