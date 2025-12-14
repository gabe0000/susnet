# UI Agent Playbook (Full Detail)

Scope: This is the full, local-reference guide for coding agents on SusNet UI + Meshtastic/AllStar integration. Local repo can include code/logs; GitHub remote remains docs-only.

Core flows
- UI root: /var/www/html/susnet/index.html (served locally). Source of truth for edits: /home/gabe0000/private-ui/susnet_index.html; deploy via sudo copy to /var/www/html/susnet/index.html. Restart services if needed with /home/gabe0000/restart_susnet.sh (local only).
- Backend: susnet_api.py (FastAPI). Meshtastic listener: /home/gabe0000/meshtastic/listener.py. Queue file: /home/gabe0000/meshtastic/queue.txt feeds listener.
- Meshtastic send path: UI -> /api/meshtastic/send -> queue line SENDJSON -> listener -> interface.sendText(channelIndex resolved by name->index).
- Channel selection is by hash (name+PSK) at radio; index is local-only. Always resolve by name using the local channel table. Listener now forces channel fetch before mapping.

UI specifics (Meshtastic)
- Message display: DM entries show “DM” + channel pills and render Sender → Recipient with long names. displayNameForNode falls back to profile nickname > from_name > topo name > ID. If names show as IDs, ensure API name map returns longName (see _mesh_name_lookup) and topology is reachable.
- Channel label display: channelLabel() maps channelIndex/name via channel_details; shows channel name instead of index.
- DM dropdown: select populated from /api/meshtastic/topology nodes (id + longName). Blank = broadcast.
- Channel dropdown: populated from topology channel_details; UI sends both channel_name and channel_index.
- Filters: DM, MQTT-only, RF-only, hide NC Mesh, channel chips. Channel prefs (mute/solo msg/TTS) stored locally and persisted via /api/meshtastic/prefs.
- Logs: messages from /api/meshtastic/messages (messages.json + name map), telemetry from /api/meshtastic/telemetry (mesh.log).

Backend notes
- _mesh_name_lookup merges fallback IDs with live `meshtastic --nodes` (JSON or table output) to supply long names. Requires TCP host reachable or serial fallback. If names regress to IDs, check the host in susnet_api.py and connectivity.
- /api/meshtastic/topology caches channel_details (name/index) for UI mapping. MESHTASTIC_CHANNELS is a list of dicts {index,name}.
- Listener: _ensure_channels_loaded() calls requestChannels + waitForConfig on startup to guarantee name->index resolution before send.

Service restart
- Use /home/gabe0000/restart_susnet.sh to restart: susnet-api, meshtastic-listener, meshtastic-aprs, dvswitch_mode_switcher, asterisk. Do not publish this script to GitHub.

Doc-only push rules
- GitHub remote (origin→https://github.com/gabe0000/susnet) is documentation only. Do not push code/logs/binaries/venv/secrets. Stage only docs; confirm with `git status --short`.

Common tasks
- Update UI: edit /home/gabe0000/private-ui/susnet_index.html, deploy via sudo cp to /var/www/html/susnet/index.html, restart services if backend touched.
- Fix name display: ensure /api/meshtastic/messages returns long names (check _mesh_name_lookup), and UI displayNameForNode/channelLabel use the name fields.
- Channel misroutes: verify channel name exists locally, listener has channels loaded, and UI sends name + index. Remember radio uses hash, not slot number.

Files to watch
- UI: /home/gabe0000/private-ui/susnet_index.html (deploy target /var/www/html/susnet/index.html)
- API: /home/gabe0000/susnet_api.py
- Listener: /home/gabe0000/meshtastic/listener.py
- Logs: /home/gabe0000/meshtastic/mesh.log, /home/gabe0000/meshtastic/messages.json
- Queue: /home/gabe0000/meshtastic/queue.txt
