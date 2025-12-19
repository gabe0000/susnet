#!/usr/bin/env bash
# Wrapper to run listener.py in the correct venv

cd /home/gabe0000/meshtastic

# Activate venv
source venv/bin/activate

# Prefer TCP to the Heltec on Wi-Fi; fall back to serial if unreachable.
export MESHTASTIC_HOST="${MESHTASTIC_HOST:-192.168.1.42}"
export MESHTASTIC_TCP_PORT="${MESHTASTIC_TCP_PORT:-4403}"

# Run the listener; exec so it replaces this shell
exec /home/gabe0000/meshtastic/listener.py
