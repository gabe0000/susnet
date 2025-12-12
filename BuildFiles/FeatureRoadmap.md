# Feature Roadmap

Rough ordering of upcoming capabilities so we keep building on what the box already does.

## Near-Term (ASAP)
- **Meshtastic UI v2 (channel controls)** – per-channel mute/solo for messaging + TTS, nicknames/notes, profiles for favorites, and cleaner filters (DM/RF/MQTT/hide-noisy channels).
- **Dire Wolf integration** – enable APRS encode/decode on a dedicated USB dongle.
- **MQTT messaging spine** – stand up a broker (Mosquitto) and publish/sub events between voice/data nodes.
- **Daily ops checklist** – document startup/shutdown, log review, UPS checks.

## Mid-Term
- **Web UI v2** – live dashboards for AllStar node status, APRS packets, Meshtastic traffic, power metrics.
- **RF TTS alerts** – convert selected APRS/Meshtastic messages to spoken alerts over a chosen channel (channel-aware mute/solo rules).
- **Replication guide** – step-by-step instructions for building another box from scratch (hardware + software).

## Long-Term
- **Automated failover** – redundant Pi or cloud-hosted AllStar node for high availability.
- **Cross-network gating rules** – configurable policies for which messages can hop between APRS, Meshtastic, and other services.
- **Telemetry analytics** – aggregate logs into a database for trend analysis (uptime, traffic volume, RF performance).

Revisit this roadmap whenever priorities shift; link each feature to GitHub issues or journal entries for context.
