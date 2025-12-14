#!/usr/bin/env python3
"""
Meshtastic listener / command daemon for Gabe's Box.

Goals:
- Own the radio link (serial by default, TCP if configured) so nothing else fights for it.
- Subscribe to all packets from the radio and:
    * Log telemetry in plain english.
    * Log text messages in a clean text log (last 1000).
    * Maintain a JSON file of recent messages (last 100) for other programs.
- Watch a simple queue file so shell commands can say:
    * "mesh send <msg>"   -> send a text into the mesh.
    * "mesh do STATUS"    -> local diagnostics printed into mesh.log.
    * easy to extend with more CMDs later.

Files used (all under ~/meshtastic):
    mesh.log          - everything (telemetry, commands, errors, etc.)
    messages.txt      - last 1000 human text messages only
    messages.json     - last 100 messages in JSON (for code)
    queue.txt         - one-shot commands from the 'mesh' shell wrapper
    my_id.txt         - our node ID (!xxxxxxxx) once we learn it
    mesh_help.txt     - human help text that 'mesh help' prints

Connection:
    - If MESHTASTIC_HOST is set, connects via TCP to that host (MESHTASTIC_TCP_PORT or 4403).
    - Otherwise connects over serial at MESHTASTIC_SERIAL_PORT or /dev/ttyUSB0.
"""

import json
import os
import signal
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import meshtastic
import meshtastic.serial_interface  # type: ignore
import meshtastic.tcp_interface  # type: ignore
from pubsub import pub  # type: ignore
from meshtastic.protobuf import channel_pb2

# --------------------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------------------

BASE_DIR = Path.home() / "meshtastic"
LOG_FILE = BASE_DIR / "mesh.log"
MESSAGES_TXT = BASE_DIR / "messages.txt"
MESSAGES_JSON = BASE_DIR / "messages.json"
QUEUE_FILE = BASE_DIR / "queue.txt"
MY_ID_FILE = BASE_DIR / "my_id.txt"
HELP_FILE = BASE_DIR / "mesh_help.txt"
TTS_NODE = "66190"
# Default: only announce direct messages to us. Set env ANNOUNCE_BROADCAST=1 to include channel broadcasts.
ANNOUNCE_BROADCAST = os.getenv("ANNOUNCE_BROADCAST", "0") == "1"
CHANNEL_PREFS_PATH = Path("/var/lib/susnet/meshtastic_prefs.json")
TTS_MIN_INTERVAL_SECONDS = 5.0  # rate-limit TTS to avoid piling on audio

# how many messages we keep
MAX_TEXT_LINES = 1000
MAX_JSON_MESSAGES = 100

# connection defaults (can be overridden with env vars)
DEFAULT_SERIAL_PORT = os.getenv("MESHTASTIC_SERIAL_PORT", "/dev/ttyUSB0")
DEFAULT_TCP_HOST = os.getenv("MESHTASTIC_HOST")  # if set, we try TCP first
DEFAULT_TCP_PORT = int(os.getenv("MESHTASTIC_TCP_PORT", "4403"))

# globals we track while running
recent_messages: List[Dict[str, Any]] = []  # last N messages for JSON file
last_metrics: Dict[str, Any] = {
    "from_id": None,
    "battery": None,
    "voltage": None,
    "uptime": None,
}
my_id: Optional[str] = None
running = True
tts_muted = False
last_tts_time = 0.0
channel_prefs_cache: Dict[str, Any] = {}
channel_prefs_ts = 0.0


# --------------------------------------------------------------------------------------
# Utility helpers
# --------------------------------------------------------------------------------------

def _ensure_channels_loaded(interface: Any) -> None:
    """
    Best-effort channel table fetch so name->index mapping works even if the
    interface did not pre-load channels.
    """
    try:
        node = getattr(interface, "localNode", None)
        if not node:
            return
        if getattr(node, "channels", None):
            return
        node.requestChannels()
        node.waitForConfig(attribute="channels")
    except Exception as e:
        _log_line(f"[WARN] Could not load channels: {e!r}")


def _ensure_dirs() -> None:
    """Make sure ~/meshtastic exists."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    CHANNEL_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    """Current time as human-readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log_line(line: str) -> None:
    """
    Append a line to mesh.log and also print to stdout so you see it
    when running interactively.
    """
    ts = _now()
    full = f"{ts} {line}"
    print(full)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(full + "\n")
    except Exception as e:
        # logging-about-logging gets old, so keep this quiet
        print(f"{ts} [LOG-ERROR] failed to write log file: {e!r}", file=sys.stderr)


def _truncate_file_to_lines(path: Path, max_lines: int) -> None:
    """Keep only the last `max_lines` of a text file."""
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= max_lines:
            return
        keep = lines[-max_lines:]
        with path.open("w", encoding="utf-8") as f:
            f.writelines(keep)
    except Exception as e:
        _log_line(f"[WARN] Failed to truncate {path}: {e!r}")


def _save_messages_json() -> None:
    """Write recent_messages to messages.json (last MAX_JSON_MESSAGES)."""
    global recent_messages
    try:
        trimmed = recent_messages[-MAX_JSON_MESSAGES:]
        with MESSAGES_JSON.open("w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2, sort_keys=True)
    except Exception as e:
        _log_line(f"[WARN] Failed to write {MESSAGES_JSON}: {e!r}")


def _append_text_message(
    from_id: str,
    to_id: str,
    text: str,
    rx_time: Optional[float] = None,
    channel: str = "Primary",
    channel_index: Optional[int] = None,
) -> None:
    """
    Record a text message in:
      - messages.txt (plain log, last 1000 lines)
      - messages.json (last 100 structured)
    """
    ts = _now()
    ch_label = channel
    if channel_index is not None:
        ch_label = f"{channel} (#{channel_index})" if channel else f"ch #{channel_index}"
    line = f"{ts} [{ch_label}] {from_id} -> {to_id}: {text}"

    # text log
    try:
        with MESSAGES_TXT.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        _log_line(f"[WARN] Failed to write {MESSAGES_TXT}: {e!r}")
    _truncate_file_to_lines(MESSAGES_TXT, MAX_TEXT_LINES)

    # json log
    msg_obj = {
        "timestamp": datetime.now().isoformat(),
        "from_id": from_id,
        "to_id": to_id,
        "text": text,
        "rxTime": rx_time,
        "channel": channel,
        "channelIndex": channel_index,
    }
    recent_messages.append(msg_obj)
    _save_messages_json()


def _read_and_clear_queue() -> List[str]:
    """
    Read queue.txt, return list of lines, then delete the file.
    If the file does not exist, returns empty list.
    """
    if not QUEUE_FILE.exists():
        return []
    try:
        with QUEUE_FILE.open("r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip()]
        QUEUE_FILE.unlink(missing_ok=True)
        return lines
    except Exception as e:
        _log_line(f"[WARN] Failed reading queue {QUEUE_FILE}: {e!r}")
        return []


def _maybe_learn_my_id_from_packet(packet: Dict[str, Any]) -> None:
    """
    As a fallback, infer our own node ID from packets:
    - When we see TELEMETRY from one node to '^all', that's almost certainly us.
    """
    global my_id
    if my_id:
        return

    from_id = packet.get("fromId")
    to_id = packet.get("toId")
    decoded = packet.get("decoded", {}) or {}
    portnum = decoded.get("portnum")

    if from_id and to_id == "^all" and portnum == "TELEMETRY_APP":
        my_id = from_id
        try:
            MY_ID_FILE.write_text(my_id + "\n", encoding="utf-8")
        except Exception as e:
            _log_line(f"[WARN] Failed to write {MY_ID_FILE}: {e!r}")
        _log_line(f"[INFO] Learned my node ID from telemetry: {my_id}")


def _try_init_my_id_from_myInfo(interface: Any) -> None:
    """
    Try to compute our node ID from interface.myInfo if present.
    If this fails for any reason we fall back to telemetry-based learning.
    """
    global my_id
    if my_id:
        return

    try:
        info = interface.myInfo
        if info and hasattr(info, "my_node_num"):
            num = info.my_node_num  # int
            mid = f"!{num:08x}"
            my_id = mid
            MY_ID_FILE.write_text(my_id + "\n", encoding="utf-8")
            _log_line(f"[INFO] Learned my node ID from myInfo: {my_id}")
    except Exception as e:
        _log_line(f"[WARN] Could not derive my_id from myInfo: {e!r}")


def _write_help_file() -> None:
    """Write mesh_help.txt explaining what this daemon does."""
    text = f"""Mesh daemon / CLI integration (listener.py)

This daemon:
  - Connects via TCP if MESHTASTIC_HOST is set (port MESHTASTIC_TCP_PORT or 4403),
    otherwise uses serial at MESHTASTIC_SERIAL_PORT or /dev/ttyUSB0.
  - Subscribes to all packets from the radio.
  - Logs:
      * Telemetry in a human friendly one-liner format.
      * Text messages in:
          - messages.txt (last {MAX_TEXT_LINES} lines, human readable)
          - messages.json (last {MAX_JSON_MESSAGES} messages, structured)
  - Watches queue.txt for commands pushed by the 'mesh' shell wrapper.

Files:
  {LOG_FILE}        - Everything the daemon sees/does (telemetry, commands, errors)
  {MESSAGES_TXT}    - Last {MAX_TEXT_LINES} text messages
  {MESSAGES_JSON}   - Last {MAX_JSON_MESSAGES} text messages as JSON
  {QUEUE_FILE}      - One-shot command queue written by 'mesh'
  {MY_ID_FILE}      - Our node ID (!XXXXXXXX) once learned
  {HELP_FILE}       - This file

Expected 'mesh' shell commands:
  mesh send <message>
      -> appends a SEND: line into queue.txt
         daemon sends it via iface.sendText(message)

  mesh do STATUS
      -> appends CMD:STATUS into queue.txt
         daemon prints a one-line status based on last telemetry

  mesh do INFO
      -> appends CMD:INFO into queue.txt
         daemon dumps interface.myInfo into mesh.log (JSON-ish)

  mesh do MUTE
      -> appends CMD:MUTE into queue.txt
         daemon suppresses AllStar TTS announcements until UNMUTE/LOUD

  mesh do UNMUTE
      -> appends CMD:UNMUTE into queue.txt
         daemon re-enables AllStar TTS announcements (alias: LOUD)

  mesh help
      -> prints this file

  mesh last 5
      -> prints the last 5 lines from messages.txt

  mesh my last 5
      -> uses messages.json + my_id.txt to show the last 5 messages
         that were addressed directly to our node (to_id == my_id).

Notes:
  - 'mesh do' is intentionally LIMITED to internal commands (STATUS, INFO, etc.)
    If you want the full python 'meshtastic' CLI surface, stop listener.py
    and run the meshtastic CLI directly so it can own the serial port.
"""
    try:
        HELP_FILE.write_text(text, encoding="utf-8")
    except Exception as e:
        _log_line(f"[WARN] Failed to write {HELP_FILE}: {e!r}")


def _load_channel_prefs(force: bool = False) -> Dict[str, Any]:
    """Load channel prefs (mute/solo for msg/TTS) and profiles."""
    global channel_prefs_cache, channel_prefs_ts
    now = time.time()
    if not force and channel_prefs_cache and (now - channel_prefs_ts) < 10:
        return channel_prefs_cache
    if not CHANNEL_PREFS_PATH.exists():
        channel_prefs_cache = {"channels": {}, "profiles": {}}
        channel_prefs_ts = now
        return channel_prefs_cache
    try:
        data = json.loads(CHANNEL_PREFS_PATH.read_text())
        channel_prefs_cache = data if isinstance(data, dict) else {"channels": {}, "profiles": {}}
    except Exception:
        channel_prefs_cache = {"channels": {}, "profiles": {}}
    channel_prefs_ts = now
    return channel_prefs_cache


def _friendly_name(node_id: Optional[str]) -> str:
    """Return a friendly name for a node if we have one."""
    if not node_id:
        return "unknown"
    nid = str(node_id).replace("!", "")
    prefs = _load_channel_prefs()
    profiles = prefs.get("profiles", {}) if isinstance(prefs, dict) else {}
    if isinstance(profiles, dict):
        prof = profiles.get(nid) or profiles.get(f"!{nid}")
        if isinstance(prof, dict):
            nick = prof.get("nickname")
            if nick:
                return nick
    return nid


def _channel_allows_tts(channel: str) -> bool:
    """Check per-channel TTS prefs: honor mute_tts and solo_tts flags."""
    prefs = _load_channel_prefs()
    channels = prefs.get("channels", {}) if isinstance(prefs, dict) else {}
    if not isinstance(channels, dict):
        channels = {}
    solo_channels = [name for name, cfg in channels.items() if isinstance(cfg, dict) and cfg.get("solo_tts")]
    cfg = channels.get(channel, {}) if isinstance(channels, dict) else {}
    if solo_channels and channel not in solo_channels:
        return False
    if isinstance(cfg, dict) and cfg.get("mute_tts"):
        return False
    return True


def _extract_channel(packet: Dict[str, Any], decoded: Dict[str, Any]) -> str:
    for key in ("channel", "channelName", "channel_name"):
        if key in packet and packet[key]:
            return str(packet[key])
        if key in decoded and decoded[key]:
            return str(decoded[key])
    return "Primary"


def _extract_channel_index(packet: Dict[str, Any], decoded: Dict[str, Any]) -> Optional[int]:
    for key in ("channelIndex", "channel_index"):
        try:
            if key in packet and packet[key] is not None:
                return int(packet[key])
            if key in decoded and decoded[key] is not None:
                return int(decoded[key])
        except Exception:
            continue
    return None


def _resolve_send_channel(
    interface: Any, channel_name: Optional[str], channel_index: Optional[int]
) -> Tuple[Optional[int], str]:
    """
    Convert a requested channel name/index into a local channel index.
    Channel indexes are local-only in Meshtastic; prefer matching by name and
    fall back to the requested index if it exists, otherwise use the primary.
    Returns (index, display_label).
    """
    resolved_idx: Optional[int] = None
    label = channel_name

    try:
        # Ensure we have channel metadata loaded for name lookups
        _ensure_channels_loaded(interface)
        node = getattr(interface, "localNode", None)
        if node and getattr(node, "channels", None):
            if channel_name:
                ch = node.getChannelByName(channel_name)
                if ch and ch.role != channel_pb2.Channel.Role.DISABLED:
                    resolved_idx = ch.index
                    label = getattr(ch.settings, "name", channel_name) or channel_name
            if resolved_idx is None and isinstance(channel_index, int):
                ch = node.getChannelByChannelIndex(channel_index)
                if ch and ch.role != channel_pb2.Channel.Role.DISABLED:
                    resolved_idx = channel_index
                    if not label:
                        label = getattr(ch.settings, "name", None)
            if resolved_idx is None:
                ch0 = node.getChannelByChannelIndex(0)
                if ch0 and ch0.role != channel_pb2.Channel.Role.DISABLED:
                    resolved_idx = 0
                    if not label:
                        label = getattr(ch0.settings, "name", None) or "Primary"
    except Exception as e:
        _log_line(f"[WARN] Channel resolution failed: {e!r}")

    if resolved_idx is None and isinstance(channel_index, int):
        resolved_idx = channel_index
    if not label:
        label = f"#{resolved_idx}" if resolved_idx is not None else "Primary"
    return resolved_idx, label


def _should_announce_inbound(from_id: str, to_id: Optional[str]) -> bool:
    """
    Decide whether an inbound text should be spoken over node 66190.

    Rules:
      - Never announce our own messages (from_id == my_id).
      - If ANNOUNCE_BROADCAST=1, also announce broadcasts to channel.
      - Always announce direct messages to *us* (to_id == my_id).
      - Do NOT announce direct messages between other nodes.
    """
    global my_id

    # Skip our own traffic (we already announced on SEND)
    if my_id and from_id == my_id:
        return False

    # Broadcasts to the channel (only if explicitly enabled)
    if ANNOUNCE_BROADCAST and (to_id is None or to_id in ("^all", "^local")):
        return True

    # Direct messages to us
    if my_id and to_id == my_id:
        return True

    # DM to someone else
    return False


def _announce_tts(text: str, tag: str, channel: str = "Primary") -> None:
    """
    Speak a string over the AllStar node with mute/rate-limit protection.
    tag: label for logging context (IN/OUT/APRS/etc).
    """
    global last_tts_time
    if tts_muted:
        _log_line(f"[ANNOUNCE-{tag}] muted; skipped '{text}'")
        return

    if not _channel_allows_tts(channel):
        _log_line(f"[ANNOUNCE-{tag}] channel {channel} muted/solo prevented TTS")
        return

    now = time.time()
    if now - last_tts_time < TTS_MIN_INTERVAL_SECONDS:
        _log_line(f"[ANNOUNCE-{tag}] rate-limited; skipped '{text}'")
        return

    last_tts_time = now
    try:
        subprocess.Popen(
            ["sudo", "asl-tts", "-n", TTS_NODE, "-t", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _log_line(f"[ANNOUNCE-{tag}] {TTS_NODE} ({channel}) <- {text}")
    except Exception as e:
        _log_line(f"[WARN] asl-tts failed: {e!r}")


# --------------------------------------------------------------------------------------
# Meshtastic callbacks
# --------------------------------------------------------------------------------------

def on_connection(interface, topic=pub.AUTO_TOPIC) -> None:  # type: ignore[override]
    """Called when we (re)connect to the radio."""
    _log_line("[INFO] Meshtastic connection established")
    _try_init_my_id_from_myInfo(interface)


def on_receive(packet: Dict[str, Any], interface) -> None:  # type: ignore[override]
    """
    Called for every packet that hits the node.
    We:
      - Decode telemetry and log in plain english.
      - Decode text messages and log/update JSON.
    """
    global last_metrics

    # ensure we have our own ID if possible
    _maybe_learn_my_id_from_packet(packet)

    from_id = packet.get("fromId", "<?>")
    to_id = packet.get("toId", None)
    rx_time = packet.get("rxTime")  # unix epoch, may be None

    decoded = packet.get("decoded", {}) or {}
    portnum = decoded.get("portnum")

    # --- TELEMETRY --------------------------------------------------------------------
    if portnum == "TELEMETRY_APP":
        telemetry = decoded.get("telemetry", {}) or {}
        metrics = telemetry.get("deviceMetrics", {}) or {}

        if not metrics:
            _log_line(f"[Telemetry] {from_id} -> {to_id}: no device metrics in this packet")
            return

        battery = metrics.get("batteryLevel")
        voltage = metrics.get("voltage")
        uptime = metrics.get("uptimeSeconds")

        if isinstance(uptime, (int, float)):
            minutes = uptime / 60.0
            hours = minutes / 60.0
            uptime_str = f"{minutes:.1f} min (~{hours:.2f} h)"
        else:
            uptime_str = "unknown"

        last_metrics = {
            "from_id": from_id,
            "battery": battery,
            "voltage": voltage,
            "uptime": uptime,
        }

        _log_line(
            f"[Telemetry] Node {from_id}: "
            f"battery {battery}% ({voltage} V), up for {uptime_str}"
        )
        return

    # --- TEXT MESSAGES ----------------------------------------------------------------
    if portnum == "TEXT_MESSAGE_APP":
        channel = _extract_channel(packet, decoded)
        ch_idx = _extract_channel_index(packet, decoded)
        # depending on version, text may be in different spots
        text = decoded.get("text")
        if text is None:
            payload = decoded.get("payload", {}) or {}
            text = payload.get("text")

        if text is None:
            _log_line(f"{ts} [Packet] TEXT_MESSAGE_APP with no text from {from_id}")
            return

        _log_line(f"[Text] {from_id} -> {to_id}: {text}")
        _append_text_message(from_id, to_id or "<?>", text, rx_time, channel, ch_idx)

        # Inbound ASL-TTS Announcement (on 66190)
        try:
            if _should_announce_inbound(from_id, to_id):
                from_name = _friendly_name(from_id)
                to_name = _friendly_name(to_id) if to_id else "channel"
                channel_label = channel or "Primary"
                if ch_idx is not None:
                    channel_label = f"{channel_label} (#{ch_idx})"
                if my_id and to_id == my_id:
                    announce_in = (
                        f"Direct Meshtastic message to this station on {channel_label}. "
                        f"From {from_name}. Message: {text}"
                    )
                elif to_id and to_id not in ("^all", "^local"):
                    announce_in = (
                        f"Meshtastic direct message on {channel_label}. "
                        f"From {from_name} to {to_name}. Message: {text}"
                    )
                else:
                    announce_in = (
                        f"Meshtastic channel message on {channel_label}. "
                        f"From {from_name}. Message: {text}"
                    )

                _announce_tts(announce_in, "IN", channel)
        except Exception as e:
            _log_line(f"[WARN] inbound asl-tts failed: {e!r}")

        return

    # --- everything else --------------------------------------------------------------
    _log_line(f"[Packet] {from_id} -> {to_id} on {portnum}")


# --------------------------------------------------------------------------------------
# Command queue processing
# --------------------------------------------------------------------------------------

def process_queue(interface: Any) -> None:
    """
    Consume queue.txt and act on each command. Supported formats:

    SEND:<text...>
        -> Send a broadcast text message to the mesh.

    CMD:STATUS
        -> Print one-line status based on last telemetry.

    CMD:INFO
        -> Dump interface.myInfo JSON-ish into mesh.log.
    """
    lines = _read_and_clear_queue()
    if not lines:
        return

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        upper = line.upper()

        # SENDJSON:{...}
        if upper.startswith("SENDJSON:"):
            try:
                payload = json.loads(line[9:])
                msg = payload.get("text", "").strip()
                dest = payload.get("dest") or None
                raw_channel = payload.get("channel")
                ch_idx = payload.get("channelIndex", raw_channel)
                ch_name = payload.get("channelName") or None
                if not ch_name and isinstance(raw_channel, str):
                    # Allow "channel" to carry a name if it's not numeric
                    try:
                        int(raw_channel)
                    except Exception:
                        ch_name = raw_channel.strip() or None
                try:
                    ch_idx = int(ch_idx) if ch_idx is not None and str(ch_idx).strip() != "" else None
                except Exception:
                    ch_idx = None
                if msg:
                    resolved_idx, resolved_label = _resolve_send_channel(interface, ch_name, ch_idx)
                    requested_label = ch_name or (f"#{ch_idx}" if ch_idx is not None else "default")
                    log_label = resolved_label or requested_label or "default"
                    if resolved_idx is not None and resolved_idx != ch_idx:
                        _log_line(
                            f"[INFO] Channel '{requested_label}' mapped to local index {resolved_idx} ({log_label})"
                        )
                    _log_line(f"[SEND] -> mesh: {msg} (dest={dest or 'broadcast'}, ch={log_label})")
                    send_ok = True
                    try:
                        kwargs = {}
                        if dest:
                            kwargs["destinationId"] = dest
                        if isinstance(resolved_idx, int):
                            kwargs["channelIndex"] = resolved_idx
                        interface.sendText(msg, **kwargs)
                    except Exception as e:
                        send_ok = False
                        _log_line(f"[ERROR] Failed to send text '{msg}': {e!r}")
                    try:
                        channel_label = log_label or "Primary"
                        dest_label = _friendly_name(dest) if dest else "channel"
                        if send_ok:
                            if dest:
                                announce_text = (
                                    f"Outbound Meshtastic direct message to {dest_label} on {channel_label}. "
                                    f"Message: {msg}"
                                )
                            else:
                                announce_text = (
                                    f"Outbound Meshtastic broadcast on {channel_label}. "
                                    f"Message: {msg}"
                                )
                        else:
                            announce_text = (
                                f"Meshtastic send may have failed. Attempted message was: {msg}"
                            )
                        _announce_tts(announce_text, "OUT", channel_label)
                    except Exception as e:
                        _log_line(f"[WARN] asl-tts failed: {e!r}")
                    try:
                        channel_label = log_label or "Primary"
                        to_label = dest or "^all"
                        _append_text_message(
                            my_id or "local",
                            to_label,
                            msg,
                            time.time(),
                            channel_label,
                            resolved_idx if isinstance(resolved_idx, int) else None,
                        )
                    except Exception as e:
                        _log_line(f"[WARN] Failed to log outbound message: {e!r}")
            except Exception as e:
                _log_line(f"[CMD] Failed to parse SENDJSON: {e!r}")
            continue

        # SEND:<msg>
        if upper.startswith("SEND:"):
            msg = line[5:].strip()
            if not msg:
                _log_line("[CMD] Ignored empty SEND: command")
                continue

            _log_line(f"[SEND] -> mesh: {msg}")
            send_ok = True
            try:
                interface.sendText(msg)
            except Exception as e:
                send_ok = False
                _log_line(f"[ERROR] Failed to send text '{msg}': {e!r}")

            # Outbound ASL-TTS on node 66190 (even if send failed, so user hears it)
            try:
                channel_label = "Primary"
                if send_ok:
                    announce_text = (
                        f"Outbound Meshtastic broadcast on {channel_label}. Message: {msg}"
                    )
                else:
                    announce_text = (
                        f"Meshtastic send may have failed. Attempted message was: {msg}"
                    )
                _announce_tts(announce_text, "OUT", channel_label)
            except Exception as e:
                _log_line(f"[WARN] asl-tts failed: {e!r}")
            continue

        # CMD:<subcommand>
        if upper.startswith("CMD:"):
            cmd = line[4:].strip().upper()
            global tts_muted

            if cmd == "STATUS":
                if not last_metrics.get("from_id"):
                    _log_line("[STATUS] No telemetry seen yet.")
                else:
                    uptime = last_metrics.get("uptime")
                    if isinstance(uptime, (int, float)):
                        minutes = uptime / 60.0
                        hours = minutes / 60.0
                        uptime_str = f"{minutes:.1f} min (~{hours:.2f} h)"
                    else:
                        uptime_str = "unknown"

                    _log_line(
                        "[STATUS] Node "
                        f"{last_metrics['from_id']}: "
                        f"battery {last_metrics['battery']}% "
                        f"({last_metrics['voltage']} V), up for {uptime_str}"
                    )
                continue

            if cmd == "INFO":
                info = getattr(interface, "myInfo", None)
                if info is None:
                    _log_line("[INFO] myInfo not available yet from device.")
                else:
                    try:
                        from meshtastic.util import message_to_json  # type: ignore
                        j = message_to_json(info)
                        _log_line(f"[INFO] myInfo: {j}")
                    except Exception:
                        _log_line(f"[INFO] myInfo (raw repr): {info!r}")
                continue

            if cmd in ("MUTE", "QUIET"):
                tts_muted = True
                _log_line("[AUDIO] TTS announcements muted")
                continue

            if cmd in ("UNMUTE", "LOUD"):
                tts_muted = False
                _log_line("[AUDIO] TTS announcements unmuted")
                continue

            _log_line(f"[CMD] Unknown command in queue: {cmd}")
            continue

        # Unrecognized line
        _log_line(f"[CMD] Unrecognized queue line: {line}")


# --------------------------------------------------------------------------------------
# Main loop / signal handling
# --------------------------------------------------------------------------------------

def _handle_sigterm(signum, frame) -> None:  # type: ignore[override]
    global running
    _log_line(f"[INFO] Received signal {signum}, shutting down.")
    running = False


def _open_interface() -> Any:
    """
    Open a Meshtastic interface.
    - If MESHTASTIC_HOST is set, try TCP first (port from MESHTASTIC_TCP_PORT or 4403).
    - Otherwise fall back to serial (port from MESHTASTIC_SERIAL_PORT or /dev/ttyUSB0).
    """
    if DEFAULT_TCP_HOST:
        try:
            _log_line(f"[INFO] Connecting via TCP {DEFAULT_TCP_HOST}:{DEFAULT_TCP_PORT}")
            return meshtastic.tcp_interface.TCPInterface(
                hostname=DEFAULT_TCP_HOST, portNumber=DEFAULT_TCP_PORT
            )
        except Exception as e:
            _log_line(f"[WARN] TCP connect failed ({DEFAULT_TCP_HOST}:{DEFAULT_TCP_PORT}): {e!r}")

    try:
        _log_line(f"[INFO] Connecting via serial {DEFAULT_SERIAL_PORT}")
        return meshtastic.serial_interface.SerialInterface(devPath=DEFAULT_SERIAL_PORT)
    except Exception as e:
        _log_line(f"[ERROR] Failed to open serial interface {DEFAULT_SERIAL_PORT}: {e!r}")
        raise


def main() -> None:
    global running

    _ensure_dirs()
    _write_help_file()

    # Subscribe to pubsub topics BEFORE connecting
    pub.subscribe(on_receive, "meshtastic.receive")
    pub.subscribe(on_connection, "meshtastic.connection.established")

    # Open the interface (TCP preferred if MESHTASTIC_HOST is set)
    interface = _open_interface()

    # Try to learn our ID from myInfo right away if possible.
    _try_init_my_id_from_myInfo(interface)
    _ensure_channels_loaded(interface)

    # Install signal handlers
    signal.signal(signal.SIGINT, _handle_sigterm)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    _log_line("[INFO] Listener main loop starting")

    while running:
        process_queue(interface)
        time.sleep(0.5)

    _log_line("[INFO] Closing Meshtastic interface")
    try:
        interface.close()
    except Exception as e:
        _log_line(f"[WARN] Error while closing interface: {e!r}")


if __name__ == "__main__":
    main()
