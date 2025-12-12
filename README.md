Here’s how I’d explain it to you.

Big Picture
- I’m building “the box”: a small always‑on comms hub (think Raspberry Pi + radios) that ties together two‑way radio voice communications (currently GMRS + Amateur Radio, but adaptable to other bands), APRS packet, and Meshtastic LoRa mesh, plus some web/API glue.
- The goal is one box that can see traffic from all these networks, log it, present it in a unified way (web/API), and eventually route/translate certain messages between them in a controlled way.

What “the box” is
- A physically small, low-power node that:
  - Bridges local conventional RF two-way radios into remote stations over VoIP by running the AllStarLink ASL3 platform with my own custom configuration.
  - Connects to an APRS feed (RF and/or APRS-IS) to see positions/messages/telemetry.
  - Connects to a Meshtastic node (LoRa) for off-grid text + position mesh.
  - Runs Python scripts and simple web/API components to log, normalize, and display everything.
- It can serve up a lightweight browser-based UI (HTML + API) for monitoring and control, but that’s optional because I can also drive it via DTMF commands over the radio and, eventually, have APRS/Meshtastic messages read over the air for nearby radios (that “speak it over RF” feature is still under construction).
- Think of it as a personal “radio gateway + message concentrator” for my local network, not a big public backbone node.

AllStar / GMRShub (and where DVSwitch fits)
- The whole box is built on the AllStarLink ASL3 image as the base OS.
- AllStar is an Asterisk-based VoIP controller for analog radios:
  - It runs on the box and talks to a USB sound interface wired into whatever two-way radio is acting as the node.
  - With my custom ASL3 configuration, that radio effectively becomes a VoIP gateway to remote AllStar/GMRShub systems.
  - My main AllStar node number is 66190.
- I have two AURSINC USB radio/audio dongles plugged into the box right now:
  - They’re half radio, half soundcard UHF transceivers: over USB they present audio/PTT, and on RF they operate as their own little simplex “hotspot” links.
  - I use them to stay away from the Pi and still talk into AllStar/GMRShub/DVSwitch; the dongle itself carries the RF path, not an external HT acting as the interface.
- GMRShub is a GMRS‑focused network built on the same Asterisk/AllStar/HamVoIP family of software:
  - It’s essentially an IP hub (or set of hubs) with GMRS‑oriented talkgroups/rooms.
  - My main GMRShub node number is 531121.
  - My GMRS node connects to GMRShub so local RF traffic can be linked to other nodes/repeaters, and vice versa.
- I also run a DVSwitch server on this box basically full time:
  - DVSwitch is an analog/digital audio bridge that connects a private AllStar node (via USRP) to many different digital voice systems.
  - That gives me a way to tie this analog AllStar/two‑way voice world (currently GMRS/ham heavy) into various digital channels and reflectors, without needing a separate dedicated digital radio for each one.
- I have a home‑grown AOIC interface board documented at https://www.mcquailertonfarms.com/pages/using-the-aoic-as-an-allstar-link-3-interface:
  - It’s a third interface I use less often, but I can plug it into the standard “K1” accessory connector (Kenwood‑style 2‑pin mic+speaker) on almost any handheld or mobile radio.
  - Because so many radios share the K1 connector, the AOIC lets me turn nearly any of them into an AllStar node interface—handy when I need more RF range than the small AURSINC dongles provide.
- In my setup overall:
  - The voice side (AllStar/GMRShub/DVSwitch) handles the human chatter—mostly GMRS and ham allocations right now, but the interfaces make it easy to swing over to other bands and radio types when needed.
  - The box’s scripts don’t decode the audio; they mostly monitor/control status, handle metadata, and make sure the nodes and links stay up and healthy.

APRS
- APRS (Automatic Packet Reporting System) is a 1200‑baud packet layer (AX.25) used for:
  - Position beacons (stations, mobiles).
  - Short messages, telemetry, and weather.
- On the box:
  - There’s an APRS listener that tails APRS data (from RF via TNC and/or APRS‑IS).
  - It parses packets into structured data (timestamp, callsign, position, text, etc.).
  - Those entries are logged and exposed so they can be viewed alongside other traffic.
- Long‑term intent:
  - Show APRS positions/messages in the same UI as Meshtastic messages.
  - Possibly forward certain APRS events into other networks (e.g., alerts, status).

Meshtastic
- Meshtastic is a LoRa mesh messaging system:
  - Low‑bandwidth, long‑range, off‑grid text and position via cheap 433/868/915 MHz modules.
  - Nodes form a mesh; your phone talks to a node via Bluetooth/Wi‑Fi.
- On the box:
  - A Meshtastic device is connected (likely over USB/serial).
  - A listener script uses the Meshtastic Python API to receive messages, positions, and telemetry and log them to files/JSON.
- Long‑term intent:
  - Normalize Meshtastic messages into the same internal format as APRS and other sources.
  - Maybe mirror certain messages to APRS (e.g., positions) or at least show them side by side.

How I’m trying to tie it all together
- Unified message pipeline:
  - APRS listener → logs structured “events”.
  - Meshtastic listener → logs structured “events”.
  - Voice/AllStar/GMRShub side → mostly status / connection events (and possibly DTMF/commands).
  - Other scripts try to merge these into a single stream or database‑like view.
- Simple web/API layer:
  - A small HTTP API and HTML page to visualize messages, positions, and status from all sources.
  - The idea is: open a browser and see “what’s going on” across the voice networks (AllStar/GMRShub/other radios), APRS, and Meshtastic in one place.
- System features I’m aiming for:
  - Always‑on logging with timestamps (for after‑the‑fact review).
  - A dashboard showing current nodes, last‑heard, battery/UPS status, maybe weather.
  - Clean separation so each radio protocol has its own listener, but the box exposes a unified interface on top.

Where I’m running into pain points
- Architecture / “the right way to do this”:
  - I’m not deeply familiar with how multi‑protocol gateways are normally structured (separate daemons, message bus, database, etc.).
  - As a result, I’m experimenting with individual scripts that read/write log files, and it’s not obvious when to evolve to a more formal architecture (e.g. one long‑running service per radio type feeding into a common queue or DB).
- Concurrency and reliability:
  - APRS, Meshtastic, and any AllStar/GMRShub control all produce events asynchronously.
  - Handling all of them at once without race conditions, dropped messages, or blocking has been tricky (how to structure loops, retries, reconnect logic, etc.).
  - Turning “a script you run once” into a robust service with logging, auto‑restart, and health checks is still new territory for me.
- Protocol/domain knowledge:
  - AllStar/GMRShub: lots of config, naming, and linking rules that are non‑obvious if you didn’t come from the ham/VoIP side.
  - APRS: understanding paths, message formats, and what should/shouldn’t be gated or rebroadcast.
  - Meshtastic: channel keys, radio parameters, and how much traffic is reasonable for the mesh.
  - I’m cautious about doing something dumb like creating loops (e.g., APRS ↔ Meshtastic) or spamming a network.
- Data modeling and mapping:
  - Each system has its own concept of identity (call sign, node ID, Meshtastic ID, etc.) and message structure.
  - I’m still working out how to represent everything in one internal schema that doesn’t lose important details but is simple enough to work with.
- General Linux/devops gaps:
  - Service management (systemd/supervisord), log rotation, permissions, and environment handling.
  - Organizing the codebase so it’s maintainable as more features get added.

In short: I’m pretty far along in wiring up the pieces and can already listen to APRS and Meshtastic and interact with the two‑way voice side via AllStar/GMRShub (currently GMRS/ham focused) from one box. The main challenges now are architectural: turning a set of working experiments into a clean, robust, multi‑protocol gateway with a sane internal data model and reliable services.

---

Docs & Samples
- `BuildFiles/` holds journals, ideas, roadmap, troubleshooting, and replication notes.
- `Sample_User_Interface.html` is a static, backend-free demo of the SusNet UI. Download and open it locally in your browser to see what the live interface looks like without exposing any services.
