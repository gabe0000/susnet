# Builder Notes

## APRS over RF using existing AllStar radio chain
- Idea: reuse the current AURSINC USB radio/soundcard transceiver dongles to transmit/receive APRS packets on UHF.
- Requirements:
  - Software TNC (Dire Wolf or Python-based AFSK generator/decoder) tied into the same audio device.
  - Arbitration between AllStar voice traffic and APRS packet bursts (pause node, key packet, release).
  - Correct audio levels/deviation; may need calibration and possibly tone-squelch changes on the HTs.
- Pros:
  - No extra RF hardware needed; leverages existing handheld and dongle.
  - Keeps APRS traffic local/private if using custom frequencies.
- Cons / open items:
  - Complexity in sharing PTT/audio with AllStar; risk of collisions.
  - Need to automate tone enable/disable if using PL tones for normal voice.
  - Might be cleaner to dedicate a second dongle/radio purely for packets.
- Next experiments:
  - Prototype Dire Wolf on the Pi and loop audio into one dongle while AllStar is idle.
  - Measure turnaround time to switch between voice and packet modes.
  - Evaluate whether an additional USB radio interface simplifies operations.

## Split voice vs. data comms across multiple Pis
- Idea: keep voice services (AllStar/GMRShub/DVSwitch) on the Pi 4B, and move APRS/Meshtastic/data listeners to the spare Pi 3B, linking them via Ethernet/MQTT.
- Networking plan:
  - Hard-wire the Pis together with Ethernet (direct cable or common switch). Modern Pis auto-negotiate, so no crossover needed.
  - Assign static IPs or run a tiny DHCP server so services always know where to find each other.
  - Keep USB-tethering as a fallback WAN link if Wi-Fi is unreliable.
- Software split:
- Voice Pi: ASL3 image, AllStar node 66190, GMRShub 531121, DVSwitch, AOIC/AURSINC interfaces (AURSINC dongles are self-contained UHF radio+soundcard units).
  - Data Pi: Dire Wolf (or similar) for APRS, Meshtastic listener, MQTT publisher/subscriber scripts, optional TTS service for RF playback.
- Messaging backbone:
  - Use MQTT topics for events (e.g., `aprs/packets`, `meshtastic/messages`, `voice/status`, `tts/requests`).
  - Both Pis subscribe/publish as needed, making the system modular and fault-tolerant.
- Benefits:
  - Cleaner resource usage per Pi; easier troubleshooting.
  - Scalability: future sensors or services can join via MQTT without touching the voice stack.
  - Allows different radios/frequencies per role without reconfiguring a single node constantly.
- Open questions:
  - How to synchronize logging/time across both Pis (NTP? shared storage?).
  - Whether to share a UPS/power management system or keep them independent.
  - Best place to host the web UI—voice Pi, data Pi, or both with load splitting.
