# 2026-02-17 NotesLM Bootstrap Journal

## Purpose
Prepare high-quality source material for Google NotesLM to generate:
- podcast deep-dive
- narrative video script
- follow-on training summaries

## Narrative Arc
1. Origin Story
- SusNet started as live operations-first tooling on a single Pi.
- Iterative "flow coding" introduced velocity and architecture drift.

2. Why This Cycle Happened
- inbound link instability required a clean, layered diagnosis model.
- need to preserve live RF while modernizing control plane.

3. Core Technical Decision
- keep host Asterisk production stable
- move diagnostics and operator surfaces into containerized V2 modules and gateway

4. What Was Built
- host inbound diagnostics routes
- V2 module/core proxy integration
- Node-RED inbound readiness + manual test controls
- docs/manual/process updates

5. Lessons Learned
- runtime/source drift is costly; sync live source before patching
- staged rollbacks prevent panic
- classify-first diagnostics are safer than auto-remediation

## Glossary
- ASL: AllStarLink
- IAX2: Inter-Asterisk eXchange v2
- CGNAT: Carrier-Grade NAT
- extnodes: external node directory file for app_rpt linking
- app_rpt: Asterisk repeater/link application module
- gateway: core API facade (`/api/*`)
- control plane: API + dashboard + orchestration layer

## NotesLM Prompt Scaffolds
- "Explain this session as a troubleshooting incident response timeline."
- "Describe tradeoffs between host RF stability and containerized control plane modernization."
- "Create an operator training segment for interpreting L1/L2/L3/L4 inbound classifications."

## Suggested Segment Titles
- "Why Inbound Failed Even While Registration Looked Healthy"
- "Designing Around Live RF: Stability-First Refactors"
- "From Ad-Hoc Logs to Structured Diagnostics"

## Reference Links
- AllStarLink docs: https://allstarlink.github.io/
- ASL Docker docs: https://allstarlink.github.io/install/debian/docker/
- GMRS active nodes endpoint: https://66.135.20.206/nodes/nodes.pl
- Meshtastic CLI docs: https://meshtastic.org/docs/software/python/cli/
- Meshtastic MQTT integration: https://meshtastic.org/docs/software/integrations/mqtt/
- Meshtastic Mosquitto notes: https://meshtastic.org/docs/software/integrations/mqtt/mosquitto/
- Meshtastic MQTT Python notes: https://meshtastic.org/docs/software/integrations/mqtt/mqtt-python/
- Meshtastic Node-RED integration: https://meshtastic.org/docs/software/integrations/mqtt/nodered/
- Tailscale funnel docs: https://tailscale.com/kb/1223/funnel
- Tailscale serve docs: https://tailscale.com/kb/1312/serve
- Node-RED docs: https://nodered.org/docs/
- ChirpStack docs: https://www.chirpstack.io/docs/
