# Troubleshooting Master Log

## Open Tickets
- TKT-1013 [] 1013 – GMRS HTTPS registration TLS CN mismatch
- TKT-1017 [] 1017 – Meshtastic channel pills show generic names (Primary/Secondary)
- TKT-1018 [critical] 1018 - Feature Add (audio UX click feedback)
- TKT-1019 [critical] 1019 - Feature Add (audio UX click feedback)
- TKT-1020 [medium] 1020 - Feature Add (audio UX click feedback)
- TKT-1021 [medium] 1021 - Feature Add (audio UX click feedback)
- TKT-1022 [medium] 1022 - Feature Add (audio UX click feedback)
- TKT-1023 [medium] 1023 - Feature Add (audio UX click feedback)
- TKT-1024 [medium] 1024 - Feature Add (audio UX click feedback)
- TKT-1025 [medium] 1025 - Feature Add (audio UX click feedback)
- TKT-1026 [medium] 1026 - Feature Add (audio UX click feedback)
- TKT-1027 [medium] 1027 - Feature Add (audio UX click feedback)
- TKT-1028 [medium] 1028 - Feature Add (audio UX click feedback)
- TKT-1029 [medium] 1029 - Feature Add (audio UX click feedback)

## Active Workstream (2026-02-17)
- Local-only inbound stabilization implemented across host API, V2 modules, and gateway.
- New endpoints:
  - `/api/allstar/inbound/health`
  - `/api/allstar/inbound/test-window`
  - `/api/gmrshub/inbound/health`
  - `/api/gmrshub/inbound/test-window`
- Node-RED V2 flow updated with inbound readiness cards and test-window buttons.
- Baseline artifacts:
  - `/home/gabe0000/backups/inbound-hardening-<timestamp>/`
  - `/home/gabe0000/backups/inbound-checks-<timestamp>/`

## Classification Taxonomy
- L1 ISP/CGNAT blocked
- L2 Router NAT/forward mismatch
- L3 Host firewall/socket issue
- L4 Asterisk auth/context/codec reject

## Closed Tickets
- TKT-1000 [low] 1000 - still only using one channel to send
- TKT-1001 [medium] 1001 - ticket numbers started over?
- TKT-1002 [medium] 1002 - ?aprs listener possibly not started at initialization
- TKT-1003 [high] 1003 - figured out messaging
- TKT-1004 [med] 1004 - node order issue
- TKT-1005 [high] 1005 - meshtastic node names
- TKT-1006 [medium] 1006 - dvswitch favorites error
- TKT-1007 [medium] 1007 - link status on allstar
- TKT-1008 [medium] 1008 - destination label wording
- TKT-1009 [high] 1009 - tts error
- TKT-1010 [medium] 1010 - aprs raw-tail cleanup
- TKT-1011 [medium] 1011 - aprs tts add
- TKT-1012 [medium] 1012 - test

## Workflow
- Create new tickets in `Troubleshooting/open/`.
- Move resolved tickets to `Troubleshooting/closed/`.
- Update this master file whenever ticket state changes or a major workstream lands.
