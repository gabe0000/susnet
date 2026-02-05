# SusNet Next Local Guide

## What is running now
- `susnet-next-portainer` on `https://susnet.local:9444`
- Portainer stacks:
  - `susnet-admin`:
    - Node-RED on `http://susnet.local:1881`
    - Node-RED Dashboard on `http://susnet.local:1881/ui/`
  - `susnet-chirpstack`:
    - ChirpStack on `http://susnet.local:8081`
    - Mosquitto on `tcp://susnet.local:1883`
    - ChirpStack Gateway Bridge on `udp://susnet.local:1701`

## Credentials location (local only)
- `/home/gabe0000/susnet-next/.secrets/initial_credentials.txt`
- Keep this file private.

## Basic daily workflow
1. Open Portainer and sign in as `admin`.
2. Go to `Stacks`.
3. Choose the app stack (`susnet-admin` or `susnet-chirpstack`).
4. Use `Stop` / `Start` / `Recreate` for lifecycle.
4. Open Node-RED and ChirpStack from their URLs above.

## Update stack config
1. Edit the target file:
   - `/home/gabe0000/susnet-next/ops/stacks/susnet-admin.compose.yml`
   - `/home/gabe0000/susnet-next/ops/stacks/susnet-chirpstack.compose.yml`
2. In Portainer: `Stacks` -> target stack -> `Editor`
3. Paste updated compose and click `Update the stack`.

## Security defaults now enforced
- Portainer HTTP UI port is disabled on host (HTTPS only on 9444).
- Node-RED editor/API requires login.
- Node-RED credential encryption secret is set.
- Node-RED seeded flow pack:
  - runtime tab: `SusNet Runtime`
  - dashboard pages: `Home`, `AllStar`, `GMRSHub`, `APRS`, `Meshtastic`, `Admin`

## Recovery quick checks
- Container status:
  - `sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'`
- Node-RED auth check:
  - `curl -si http://127.0.0.1:1881/flows | head`
  - should return `401 Unauthorized` without token.
