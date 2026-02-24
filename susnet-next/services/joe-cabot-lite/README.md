# Joe Cabot Lite Service Source

This directory is the tracked source of truth for the host runtime deployed at:
- `/home/codex/joe-cabot-lite`

## Files
- `joe_cabot_lite.py` service runtime
- `ask_joe.py` operator CLI helper
- `requirements.txt` Python dependencies
- `Dockerfile` and `docker-compose.yml` retained for parity/portability

## Deploy
From repo root:
```bash
./scripts/deploy-joe-cabot-lite.sh
```

This syncs tracked source to `/home/codex/joe-cabot-lite`, ensures venv dependencies, compiles, and restarts `joe-cabot-lite.service`.
