# Deployment notes (susnet.local)

- UI: source file lives at `/home/gabe0000/susnet_index.html` (private UI at `/home/gabe0000/private-ui/susnet_index.html`). Deploy to the live site with `sudo cp /home/gabe0000/susnet_index.html /var/www/html/susnet/index.html`.
- API: live service runs from `/opt/susnet-api/susnet_api.py` via systemd unit `susnet-api.service`. After copying in changes (`sudo cp /home/gabe0000/susnet_api.py /opt/susnet-api/susnet_api.py`), restart with `sudo systemctl restart susnet-api`.
- Meshtastic listener: runs `/home/gabe0000/meshtastic/listener.py` via `meshtastic-listener.service`. Restart after edits with `sudo systemctl restart meshtastic-listener`.
- Live site URL: https://susnet.local/susnet/ (served from `/var/www/html/susnet/`).
- APRS/Meshtastic logs/data live under `/home/gabe0000/meshtastic` and `/home/gabe0000/aprs`.
