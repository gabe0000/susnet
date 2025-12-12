# Idea Backlog & Pipeline

Track every concept here so it can move from brainstorming → prototype → production feature. When an idea graduates, reference the commit/branch where it lives.

## Funnel Stages
1. **Spark** – raw idea or problem statement.
2. **Research** – notes, links, experiments.
3. **Prototype** – proof-of-concept scripts/configs.
4. **Integrate** – merged into the main stack with docs/tests.

## Current Ideas

### Split Voice/Data Nodes via MQTT Backbone (Spark → Research)
- Description: dedicate the Pi 4B to AllStar/GMRShub/DVSwitch and run APRS/Meshtastic/TTS services on the Pi 3B, connected over Ethernet + MQTT.
- Next actions: design MQTT topic map, decide which node hosts the web UI, define synchronization requirements (time, logging).

### APRS over RF using Existing AllStar Hardware (Spark)
- Description: reuse an AURSINC UHF radio/soundcard transceiver dongle to carry APRS packets on a private UHF channel (hotspot/simplex style).
- Next actions: test Dire Wolf audio with the dongle, plan PTT arbitration or dedicate a second packet-only dongle, document tone-squelch implications.

### RF Audio Read-Out for APRS/Meshtastic (Research)
- Description: optional feature where important data messages are spoken over RF via TTS.
- Next actions: choose TTS engine, define DTMF control codes, ensure messages don’t loop back into gateways.

### Web UI Enhancements (Spark)
- Description: extend the browser interface to show live voice link states, APRS/Meshtastic maps, and system health.
- Next actions: evaluate lightweight frameworks (Flask/FastAPI + HTMX?), define API endpoints, sync with MQTT bus.

Add more entries as soon as a new idea pops up—even if it’s half-baked.
