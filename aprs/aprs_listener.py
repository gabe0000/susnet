#!/usr/bin/env python3
"""
APRS-IS listener that watches for messages addressed to a target callsign
and logs them. No AllStar/TTS integration.

Configuration (env vars or /etc/default/aprs-listener when run via systemd):
  APRS_CALLSIGN   - your APRS-IS login callsign-SSID (required)
  APRS_PASSCODE   - APRS-IS passcode (required)
  APRS_SERVER     - APRS-IS host (default rotate.aprs.net)
  APRS_PORT       - APRS-IS port (default 14580)
  APRS_TARGET     - callsign-SSID to announce (default W4VDX-9)
  APRS_FILTER     - APRS-IS filter string (default: p/<target>,t/m)
  APRS_WATCH      - substring to match (case-insensitive) before logging (default W4VDX)

Writes logs to aprs.log in the same directory as this script.
"""

import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import subprocess

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "aprs.log"

DEFAULT_SERVER = "rotate.aprs.net"
DEFAULT_PORT = 14580
DEFAULT_TARGET = "W4VDX-9"
DEFAULT_FILTER = None  # will be built from target if not provided
DEFAULT_WATCH = "W4VDX"
APRS_TTS_ENABLED = str(os.getenv("APRS_TTS", "0")).lower() in ("1", "true", "yes", "on")
APRS_TTS_NODE = os.getenv("APRS_TTS_NODE") or os.getenv("SUSNET_TTS_NODE") or "66190"


def _now() -> str:
    # Friendly 12-hour format: DD/MM/YYYY HH:MM AM/PM
    return datetime.now().strftime("%d/%m/%Y %I:%M %p")


def _log(line: str) -> None:
    ts = _now()
    full = f"{ts} {line}"
    print(full)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(full + "\n")
    except Exception:
        # avoid recursive logging on failure
        pass


def _speak(text: str) -> None:
    if not APRS_TTS_ENABLED or not text:
        return
    try:
        cleaned = text.replace("APRS", "A.P.R.S.")
        subprocess.Popen(
            ["sudo", "asl-tts", "-n", APRS_TTS_NODE, "-t", cleaned],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _parse_aprs_message(line: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Return (src, addressee, message, path) for APRS message frames of the form
    SRCCALL>PATH:ADDRESSEE:message
    """
    m = re.match(r"^([^>]+)>([^:]+):([^:]+):(.*)$", line)
    if not m:
        return None
    src = m.group(1).strip()
    path = m.group(2).strip()
    addressee = m.group(3).strip()
    msg = m.group(4).strip()
    if "{" in msg:
        msg = msg.split("{", 1)[0].strip()
    return src, addressee, msg, path


def _build_login_line(callsign: str, passcode: str, filter_str: str) -> str:
    return f"user {callsign} pass {passcode} vers aprs-listener 0.1 filter {filter_str}\n"


def main() -> None:
    server = os.getenv("APRS_SERVER", DEFAULT_SERVER)
    port = int(os.getenv("APRS_PORT", DEFAULT_PORT))
    callsign = os.getenv("APRS_CALLSIGN")
    passcode = os.getenv("APRS_PASSCODE")
    target = os.getenv("APRS_TARGET", DEFAULT_TARGET)
    filter_str = os.getenv("APRS_FILTER") or f"p/{target},t/m"
    watch_substr = os.getenv("APRS_WATCH", DEFAULT_WATCH)

    if not callsign or not passcode:
        _log("[ERROR] APRS_CALLSIGN/APRS_PASSCODE not set; export them or use /etc/default/meshtastic-aprs")
        sys.exit(1)

    _log(
        f"[INFO] Starting APRS listener: server={server}:{port}, target={target}, filter={filter_str}"
    )

    while True:
        try:
            _log(f"[INFO] Connecting to APRS-IS {server}:{port}")
            sock = socket.create_connection((server, port), timeout=30)
            f = sock.makefile("r", encoding="utf-8", errors="ignore")
            login = _build_login_line(callsign, passcode, filter_str)
            sock.sendall(login.encode("utf-8"))
            _log("[INFO] Login sent to APRS-IS")

            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                # APRS-IS may send status lines starting with '#'
                if line.startswith("#"):
                    if "logresp" in line.lower():
                        _log(f"[INFO] APRS-IS {line}")
                    continue

                parsed = _parse_aprs_message(line)
                if not parsed:
                    continue

                src, addressee, msg, path = parsed
                target_match = addressee.upper() == target.upper()
                watch_match = watch_substr and watch_substr.lower() in line.lower()
                if not (target_match or watch_match):
                    continue

                _log(f"[APRS] {src} -> {addressee} | path={path}: {msg}")
                _speak(f"APRS message from {src} to {addressee}: {msg}")

        except Exception as e:
            _log(f"[WARN] Connection error: {e!r}, retrying in 10s")
            time.sleep(10)
            continue


if __name__ == "__main__":
    main()
