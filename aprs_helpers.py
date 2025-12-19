#!/usr/bin/env python3
import os
import json
import time
import math
import subprocess

import requests

# =========================
# CONFIG
# =========================

APRSFI_API_KEY = os.environ.get("APRSFI_API_KEY")
APRSFI_URL = "https://api.aprs.fi/api/get"

# This MUST identify your app, per aprs.fi TOS
USER_AGENT = "FarmNetPi/0.1 (+https://example.com/farmnet-node)"

# Where to remember which messages you've already read
STATE_FILE = "/var/lib/aprs_msg_state.json"   # change if permissions are an issue

# ---- TTS / AllStar integration ----
# Change this to whatever you already use to make the node talk.
# Example assumption: /usr/local/sbin/say_text <node> "<message>"
TTS_COMMAND = ["/usr/local/sbin/say_text", "66190"]


# =========================
# Utilities
# =========================

def ensure_api_key():
    if not APRSFI_API_KEY:
        raise RuntimeError("APRSFI_API_KEY environment variable not set.")


def aprs_get(params):
    """Low-level helper to call aprs.fi API and return decoded JSON dict."""
    ensure_api_key()
    full_params = dict(params)
    full_params["apikey"] = APRSFI_API_KEY
    full_params["format"] = "json"

    headers = {"User-Agent": USER_AGENT}

    resp = requests.get(APRSFI_URL, params=full_params, headers=headers, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    if data.get("result") != "ok":
        raise RuntimeError(f"aprs.fi returned error: {data.get('description')}")

    return data


def get_messages_to(dst_call):
    """Return list of message entries (latest, max 10) destined to dst_call."""
    data = aprs_get({
        "what": "msg",
        "dst": dst_call.upper(),
    })
    return data.get("entries", [])


def get_last_location(name):
    """Return the latest location entry for a station, or None."""
    data = aprs_get({
        "what": "loc",
        "name": name.upper(),
    })
    entries = data.get("entries", [])
    if not entries:
        return None
    # They’re usually already latest, but sort by lasttime just in case
    entries.sort(key=lambda e: int(e.get("lasttime", 0)), reverse=True)
    return entries[0]


def get_weather_for_stations(station_names):
    """Return wx entries for one or more stations (max 20)."""
    if not station_names:
        return []

    name_str = ",".join(station_names)
    data = aprs_get({
        "what": "wx",
        "name": name_str,
    })
    return data.get("entries", [])


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def speak(text):
    """Send text to your existing AllStar TTS pipeline."""
    if not text:
        return
    try:
        # Append the message text to the command
        cmd = TTS_COMMAND + [text]
        subprocess.run(cmd, check=False)
    except Exception as e:
        # We don't want TTS failures to crash the script
        print(f"[WARN] TTS failed: {e}")


# =========================
# Geo helpers (for weather)
# =========================

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points in km."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def c_to_f(temp_c):
    return (temp_c * 9.0 / 5.0) + 32.0


def ms_to_mph(ms):
    return ms * 2.23693629


def wind_direction_to_cardinal(deg):
    """Return rough cardinal direction from degrees."""
    if deg is None:
        return None
    dirs = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
    ix = int((deg % 360) / 45.0 + 0.5) % 8
    return dirs[ix]
