# Replication Guide (Work in Progress)

Document everything needed to build "the box" from scratch. Expand each section as you validate the steps.

## Hardware Checklist
- Raspberry Pi 4B (voice) + microSD + UPS HAT.
- Optional Raspberry Pi 3B (data) for APRS/Meshtastic workloads.
- Two AURSINC USB radio/audio interfaces (or equivalent soundcard/PTT dongles).
- AOIC interface board for K1-style radios (optional but boosts range).
- HTs or mobiles for each RF role (voice vs. packet) plus antennas/duplexers.
- Ethernet cable(s) for Pi-to-Pi linking; optional USB tethering cable.

## Base Imaging
1. Flash AllStarLink ASL3 onto the Pi 4B SD card.
2. Apply custom configuration (node 66190, GMRShub 531121, DVSwitch install).
3. For the data Pi, start from Raspberry Pi OS Lite, then install Meshtastic CLI, Dire Wolf, MQTT client libraries.

## Software Stack Overview
- **Voice Pi:** AllStar node services, GMRShub link scripts, DVSwitch, monitoring agents, DTMF command handler.
- **Data Pi:** APRS listener/gateway, Meshtastic listener, MQTT broker/client, optional TTS service, web UI backend (if hosted here).

## Configuration Steps (To Do)
- Wiring diagrams for AURSINC dongles + HTs, including tone settings.
- Systemd service files for APRS listener, Meshtastic listener, MQTT bridge.
- Security hardening (firewall, VPN, credential storage).

## Validation Checklist
- AllStar links connect outbound/inbound; DTMF commands respond.
- APRS packets heard, parsed, and mirrored to logs/UI.
- Meshtastic events ingested; MQTT queue shows traffic.
- Browser UI reachable; fallback DTMF controls verified.

Fill in missing sections as you replicate the build or help someone else do it.
