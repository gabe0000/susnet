# UI Human Guide (Comprehensive)

Purpose: How to operate the SusNet web UI and Meshtastic messaging, with local details.

Locations
- Web UI: open https://susnet.local/susnet/ (served from /var/www/html/susnet/index.html).
- Source for UI edits: /home/gabe0000/private-ui/susnet_index.html (don’t change unless you’re updating the UI).
- Restart all services if things look stale: run /home/gabe0000/restart_susnet.sh (local helper).

Meshtastic usage
- Messages pane shows channel (or “DM”), sender → recipient for direct messages, path (RF/MQTT), timestamp, and body. The UI auto-refreshes messages/telemetry about every 5 seconds and also right after you send.
- Names: should display friendly names; if an ID like !9e77f1a0 shows, the backend couldn’t resolve the name yet (usually connectivity to the node list).
- Sending messages:
  - “Dest (optional)” dropdown: pick a node for a direct message, or leave blank for channel broadcast.
  - “Channel” dropdown: choose the channel. The system sends on that channel using the channel’s hash (name+PSK), so it works even if slot numbers differ across radios.
  - Type your text and click Send.
- Filters: chips let you show DMs only, MQTT-only, RF-only, hide NC Mesh, or pick a channel. Search box filters by text or sender name.
- Channel preferences: click gear next to a channel to set mute/solo for messaging or TTS.

Telemetry
- Telemetry pane lists recent telemetry lines from mesh.log (battery, voltage, uptime). Auto-refreshes on “Refresh” or full page reload.

APRS, AllStar, DVSwitch
- APRS: view activity, set filters, send APRS messages (call/SSID and text).
- AllStar/DVSwitch: nodes/modes lists pull from local configs; use buttons to connect/disconnect or set modes.

Troubleshooting quick tips
- UI looks outdated: run /home/gabe0000/restart_susnet.sh to refresh services; hard-refresh the browser (Ctrl+Shift+R).
- Names show as IDs: likely lost node directory; try Refresh (Meshtastic) to reload topology; ensure the radio is reachable.
- Channel misroute: ensure you chose the correct channel name; the system matches channels by hash, not slot number, so name/PSK must match the other device.

What not to do
- Don’t edit files under /var/www/html/susnet directly unless you know you’re deploying a new UI (use the source in /home/gabe0000/private-ui).
- Don’t push code/logs to GitHub; that remote is docs-only.
