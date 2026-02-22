# Susnet

Susnet is the control-plane host for the Reservoir Pi(s) system.

Current live role:
- hosts Joe Cabot (lightweight control-plane assistant)
- hosts OpenClaw + Ollama local model runtime
- consumes edge MQTT events from MeshBox (`Mr. Pink`)
- provides direct operator query/reply path over MQTT

## Runtime Identity
- Hostname: `susnet`
- Tailscale IPv4: `susnet`
- OS: Debian GNU/Linux 12 (bookworm)
- Architecture: `aarch64`

## Start Here
- `docs/QUICKSTART.md`
- `docs/owners-manual/README.md`
- `docs/JOURNAL.md`

## Canonical Program Docs
- Reservoir Pi(s): `https://github.com/gabe0000/resevoir-pis`
