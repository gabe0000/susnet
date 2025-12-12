# Design Considerations & Constraints

Keep this document updated as requirements change. It should guide future hardware and software decisions.

## Functional Goals
1. Bridge local RF voice radios to remote networks (AllStar/GMRShub/DVSwitch) reliably.
2. Collect, normalize, and display APRS + Meshtastic data.
3. Offer both browser-based and radio-based (DTMF/audio) control paths.
4. Remain portable and reproducible so another builder can duplicate "the box."
5. Support per-channel controls (mute/solo for messaging and TTS) and human-friendly nicknames/notes for Meshtastic nodes.

## Constraints
- Power budget: optimized for Pi-class SBCs with UPS HAT support.
- Connectivity: must tolerate flaky WAN; local MQTT/Ethernet between modules is preferred.
- Modularity: voice vs. data components should be separable (even separate Pis) without breaking workflows.
- Regulatory: respect band allocations (GMRS vs Amateur) and avoid unintended cross-band retransmissions.

## Open Design Questions
- Best storage backend for unified logs/events? (SQLite vs. flat files vs. MQTT retention)
- Which services should expose REST vs. MQTT vs. CLI interfaces?
- Process supervision: systemd on each Pi, or containerization?

Update sections as you discover new limitations or make decisions.
