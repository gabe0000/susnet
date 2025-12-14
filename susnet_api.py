from __future__ import annotations

import configparser
import json
import math
import os
import re
import subprocess
import time
from datetime import datetime
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_TITLE = "SusNet Local API"
VERSION = "0.3.1"

AST_BIN = "/usr/sbin/asterisk"
ALLMON3_INI = Path("/etc/allmon3/allmon3.ini")
FAVORITES_PATH = Path("/var/lib/susnet/favorites.json")
STATE_PATH = Path("/var/lib/susnet/state.json")

MESHTASTIC_BASE = Path("/home/gabe0000/meshtastic")
MESHTASTIC_MESSAGES = MESHTASTIC_BASE / "messages.txt"
MESHTASTIC_LOG = MESHTASTIC_BASE / "mesh.log"
APRS_LOG = Path("/home/gabe0000/aprs/aprs.log")
QUEUE_FILE = MESHTASTIC_BASE / "queue.txt"
MESHTASTIC_CLI = "/opt/susnet-api/venv/bin/meshtastic"
MESHTASTIC_TIMEOUT = 8
MESHTASTIC_PORT = "/dev/ttyUSB0"
_tcp_host_file = MESHTASTIC_BASE / "tcp_host.txt"
MESHTASTIC_HOST = os.getenv("MESHTASTIC_HOST")
if not MESHTASTIC_HOST and _tcp_host_file.exists():
    try:
        MESHTASTIC_HOST = _tcp_host_file.read_text().strip() or None
    except Exception:
        MESHTASTIC_HOST = None
if not MESHTASTIC_HOST:
    MESHTASTIC_HOST = "192.168.1.42"  # fallback to the known Wi-Fi node
MESHTASTIC_TCP_PORT = int(os.getenv("MESHTASTIC_TCP_PORT", "4403"))
MESHTASTIC_JSON = MESHTASTIC_BASE / "messages.json"
MESHTASTIC_MY_ID = MESHTASTIC_BASE / "my_id.txt"
MESHTASTIC_SERIAL_LINK = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
TTS_NODE = os.getenv("SUSNET_TTS_NODE", "66190")
MESHTASTIC_CHANNELS: List[Dict[str, Any]] = []

TROUBLE_ROOT = Path("/home/gabe0000/Troubleshooting")
TROUBLE_OPEN = TROUBLE_ROOT / "open"
TROUBLE_CLOSED = TROUBLE_ROOT / "closed"
TROUBLE_MASTER = TROUBLE_ROOT / "master.md"

MODE_SWITCHER_URL = "http://127.0.0.1:3000"
MODE_ALIAS_FILE = Path("/opt/dvswitch_mode_switcher/configs/tg_alias.yml")

APRS_CALLSIGN = "W4VDX-10"
APRS_ENV_FILE = Path("/etc/default/meshtastic-aprs")
APRS_DEFAULT_WATCH = "W4VDX"
APRS_DEFAULT_ZIP = "28001"
APRS_DEFAULT_RADIUS_MI = 100

TARGET_NODE_RE = re.compile(r"\b(\d{3,7})\b")


class LinkRequest(BaseModel):
    localNode: int = Field(..., ge=1)
    target: int = Field(..., ge=1)
    mode: str = Field("perm", description="perm|monitor")


class LocalRequest(BaseModel):
    localNode: int = Field(..., ge=1)


class FavoriteRequest(BaseModel):
    scope: str = Field(..., pattern="^(node|mode|mesh)$")
    key: str
    id: str
    label: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class DeleteFavoriteRequest(BaseModel):
    scope: str = Field(..., pattern="^(node|mode|mesh)$")
    key: str
    id: str


class ModeSelectRequest(BaseModel):
    mode: str
    tgid: Optional[str] = None


class SendRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=240)
    dest: Optional[str] = None
    channel: Optional[str] = Field(None, description="Channel name or index (legacy)")
    channel_index: Optional[int] = Field(None, description="Channel index for Meshtastic send")
    channel_name: Optional[str] = Field(None, description="Channel name label")


class AprsConfigRequest(BaseModel):
    zip: str = Field(..., min_length=3, max_length=10)
    radius_miles: float = Field(..., gt=0, lt=1000)
    watch: str = Field(..., min_length=2, max_length=12)
    target: Optional[str] = None
    callsign: Optional[str] = None


class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=32)


class TicketCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=3, max_length=2000)
    subsystem: Optional[str] = Field(None, max_length=64)
    severity: Optional[str] = Field("medium", max_length=32)


class TicketCloseRequest(BaseModel):
    resolution: Optional[str] = Field("", max_length=2000)
    followup: Optional[str] = Field("", max_length=2000)


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=240)
    node: Optional[str] = Field(None, description="AllStar node to send TTS to")


app = FastAPI(title=APP_TITLE, version=VERSION)

# Local-only use; allow same-LAN browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr.strip() or str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_asterisk(command: str) -> str:
    return _run([AST_BIN, "-rx", command])


def _run_meshtastic(args: List[str]) -> Optional[str]:
    errors = []
    # Try TCP first if configured
    if MESHTASTIC_HOST:
        cmd = ["timeout", str(MESHTASTIC_TIMEOUT), MESHTASTIC_CLI, "--host", f"{MESHTASTIC_HOST}"] + args
        try:
            return _run(cmd)
        except HTTPException as e:
            errors.append(f"tcp: {e.detail}")
    # Fall back to serial
    port = MESHTASTIC_SERIAL_LINK if Path(MESHTASTIC_SERIAL_LINK).exists() else MESHTASTIC_PORT
    cmd = ["timeout", str(MESHTASTIC_TIMEOUT), MESHTASTIC_CLI, "--port", port] + args
    try:
        return _run(cmd)
    except HTTPException as e:
        errors.append(f"serial: {e.detail}")
    return None


def _speak_tts(text: str, node: Optional[str] = None) -> None:
    """Fire-and-forget TTS using the same pipeline as the listener."""
    target_node = str(node or TTS_NODE)
    if not text:
        return
    try:
        subprocess.Popen(
            ["sudo", "asl-tts", "-n", target_node, "-t", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # Do not raise to caller; TTS should never block main flow
        pass


def _safe_int(val: Any) -> Optional[int]:
    try:
        return int(str(val).strip())
    except Exception:
        return None


def _channel_index_from_cache(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    name_lower = name.strip().lower()
    for ch in MESHTASTIC_CHANNELS:
        if not isinstance(ch, dict):
            continue
        ch_name = str(ch.get("name") or "").strip().lower()
        if ch_name == name_lower:
            idx = ch.get("index")
            try:
                return int(idx) if idx is not None else None
            except Exception:
                return None
    return None


def _extract_channel_names(raw_info: str) -> List[str]:
    """Best-effort channel name extraction from meshtastic --info output."""
    names: List[str] = []
    seen = set()
    if not raw_info:
        return names
    # Prefer explicit JSON-style name fields
    for match in re.finditer(r'"name":\s*"([^"]+)"', raw_info):
        name = match.group(1).strip()
        if name and name.lower() not in ("true", "false") and name not in seen:
            seen.add(name)
            names.append(name)
    if names:
        return names
    # Fallback: text lines containing "Channel" or "Index"
    for line in raw_info.splitlines():
        line_stripped = line.strip()
        if (line_stripped.startswith("Channel") or line_stripped.startswith("Index")) and ":" in line_stripped:
            ch = line_stripped.split(":", 1)[1].strip()
            if ch and ch.lower() not in ("true", "false") and ch not in seen:
                seen.add(ch)
                names.append(ch)
    return names


def _parse_channel_details(raw_info: str, fallback_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Try to recover channel index/name pairs from meshtastic --info output.
    Returns a list of {"index": int|None, "name": str}.
    """
    details: List[Dict[str, Any]] = []
    seen_idx = set()
    seen_name = set()

    def add(idx: Optional[int], name: Optional[str]) -> None:
        if not name:
            return
        name_clean = str(name).strip()
        if not name_clean:
            return
        # If we already have this exact index, prefer the first occurrence
        if idx is not None and idx in seen_idx:
            return
        # Avoid duplicates by name too
        key = name_clean.lower()
        if key in seen_name and idx is None:
            return
        details.append({"index": idx, "name": name_clean})
        if idx is not None:
            seen_idx.add(idx)
        seen_name.add(key)

    if raw_info:
        try:
            data = json.loads(raw_info)
            if isinstance(data, dict):
                for key in ("channels", "channelSettings", "channel_settings", "secondary_channels"):
                    arr = data.get(key)
                    if isinstance(arr, list):
                        for entry in arr:
                            if not isinstance(entry, dict):
                                continue
                            settings = entry.get("settings") if isinstance(entry.get("settings"), dict) else None
                            name = entry.get("name") or (settings.get("name") if settings else None)
                            idx = _safe_int(entry.get("index"))
                            add(idx, name)
        except Exception:
            pass

        # Regex fallback to capture "index: X ... name: Y" inline
        for match in re.finditer(
            r'index["\s]*[:=]\s*(\d+)[^\n\r]*?name["\s]*[:=]\s*"([^"]+)"', raw_info, flags=re.IGNORECASE
        ):
            add(_safe_int(match.group(1)), match.group(2))

        for line in raw_info.splitlines():
            match = re.search(r"\bIndex\s+(\d+)\s*[:=]\s*(.+)", line, flags=re.IGNORECASE)
            if match:
                idx = _safe_int(match.group(1))
                name_part = match.group(2).strip()
                # Trim off extra metadata after double spaces or commas
                name_part = re.split(r"\s{2,}|\spsk|,", name_part, 1)[0].strip()
                add(idx, name_part)

    if not details and fallback_names:
        for idx, name in enumerate(fallback_names):
            add(idx, name)

    return details


def _parse_nodes_table(raw: str) -> List[Dict[str, str]]:
    """Parse plain meshtastic --nodes table output."""
    parsed: List[Dict[str, str]] = []
    seen = set()
    for line in raw.splitlines():
        if not line.startswith("│"):
            continue
        cols = [c.strip() for c in line.strip("│").split("│")]
        if len(cols) < 3 or cols[0].startswith("N") or cols[1] == "User":
            continue
        user = cols[1]
        node_id = cols[2]
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        parsed.append({"id": node_id, "name": user or node_id})
    return parsed


def _collect_mesh_ids_fallback() -> List[Dict[str, str]]:
    seen: Dict[str, str] = {}
    # my_id file if present
    if MESHTASTIC_MY_ID.exists():
        try:
            mid = MESHTASTIC_MY_ID.read_text().strip()
            if mid:
                seen[mid] = mid
        except Exception:
            pass
    # structured messages.json
    if MESHTASTIC_JSON.exists():
        try:
            data = json.loads(MESHTASTIC_JSON.read_text())
            for msg in data if isinstance(data, list) else data.get("messages", []):
                for key in ("from_id", "to_id", "fromId", "toId"):
                    val = msg.get(key) if isinstance(msg, dict) else None
                    if isinstance(val, str) and val and val != "^all":
                        seen[val] = seen.get(val, val)
        except Exception:
            pass
    # plain text messages.txt
    for line in _tail_lines(MESHTASTIC_MESSAGES, 500):
        for token in re.findall(r"([!A-Za-z0-9]{3,12})", line):
            if token and token != "^all":
                seen[token] = seen.get(token, token)
    return [{"id": k, "name": v} for k, v in seen.items()]


# --- Troubleshooting tickets helpers ---
def _ensure_trouble_dirs() -> None:
    TROUBLE_ROOT.mkdir(parents=True, exist_ok=True)
    TROUBLE_OPEN.mkdir(parents=True, exist_ok=True)
    TROUBLE_CLOSED.mkdir(parents=True, exist_ok=True)


def _parse_ticket_meta(path: Path) -> Dict[str, Any]:
    meta = {
        "id": path.stem,
        "title": "",
        "date_opened": "",
        "date_closed": "",
        "subsystem": "",
        "severity": "",
        "status": "open",
    }
    try:
        lines = path.read_text().splitlines()
    except Exception:
        return meta
    if lines:
        if lines[0].startswith("#"):
            # Format: # TKT-1001 - Title text
            parts = lines[0].split("-", 1)
            if len(parts) == 2:
                meta["title"] = parts[1].strip()
    for line in lines[:30]:
        if line.startswith("- Date opened:"):
            meta["date_opened"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Date closed:"):
            meta["date_closed"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Subsystem:"):
            meta["subsystem"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Severity:"):
            meta["severity"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Status:"):
            meta["status"] = line.split(":", 1)[1].strip()
    return meta


def _next_ticket_id() -> str:
    _ensure_trouble_dirs()
    max_id = 999
    for p in list(TROUBLE_OPEN.glob("TKT-*.md")) + list(TROUBLE_CLOSED.glob("TKT-*.md")):
        try:
            num = int(p.stem.replace("TKT-", ""))
            max_id = max(max_id, num)
        except ValueError:
            continue
    return f"TKT-{max_id + 1}"


def _rewrite_master(open_items: List[Dict[str, Any]], closed_items: List[Dict[str, Any]]) -> None:
    lines: List[str] = [
        "# Troubleshooting Master Log",
        "",
        "## Open Tickets",
    ]
    if not open_items:
        lines.append("- (none)")
    else:
        for t in sorted(open_items, key=lambda x: x.get("id", "")):
            lines.append(
                f"- {t.get('id','')} [{t.get('severity','')}] {t.get('title','')} (subsystem: {t.get('subsystem','')}, opened: {t.get('date_opened','')})"
            )
    lines.append("")
    lines.append("## Closed Tickets")
    if not closed_items:
        lines.append("- (none)")
    else:
        for t in sorted(closed_items, key=lambda x: x.get("id", "")):
            lines.append(
                f"- {t.get('id','')} [{t.get('severity','')}] {t.get('title','')} (closed: {t.get('date_closed','')})"
            )
    lines.append("")
    lines.append("## Workflow")
    lines.append("- Create new tickets in `Troubleshooting/open/` (one file per ticket).")
    lines.append("- When resolved, move to `Troubleshooting/closed/` and update status/meta.")
    TROUBLE_MASTER.write_text("\n".join(lines))


def _collect_tickets(status: str) -> List[Dict[str, Any]]:
    _ensure_trouble_dirs()
    if status == "open":
        paths = sorted(TROUBLE_OPEN.glob("TKT-*.md"))
    elif status == "closed":
        paths = sorted(TROUBLE_CLOSED.glob("TKT-*.md"))
    else:
        paths = sorted(TROUBLE_OPEN.glob("TKT-*.md")) + sorted(TROUBLE_CLOSED.glob("TKT-*.md"))
    return [_parse_ticket_meta(p) for p in paths]


def _update_master_from_fs() -> None:
    open_items = _collect_tickets("open")
    closed_items = _collect_tickets("closed")
    _rewrite_master(open_items, closed_items)


def _sanitize_line(text: str) -> str:
    return text.replace("\n", " ").strip()


def _collect_node_activity() -> Dict[str, Dict[str, Any]]:
    """Scan mesh.log for last activity and whether it came via MQTT."""
    activity: Dict[str, Dict[str, Any]] = {}
    lines = _tail_lines(MESHTASTIC_LOG, 2000)
    for line in lines:
        ts_match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if not ts_match:
            continue
        try:
            ts = int(datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S").timestamp())
        except Exception:
            continue
        ids = re.findall(r"!([0-9a-fA-F]{6,8})", line)
        if not ids:
            continue
        via_mqtt = "viamqtt" in line.lower()
        for nid in ids:
            entry = activity.setdefault(nid if nid.startswith("!") else f"!{nid}", {"last": 0, "via_mqtt": False})
            if ts > entry["last"]:
                entry["last"] = ts
            if via_mqtt:
                entry["via_mqtt"] = True
    return activity


def _parse_connected(output: str, local: int) -> List[int]:
    connected: List[int] = []
    for line in output.splitlines():
        for match in TARGET_NODE_RE.findall(line):
            num = int(match)
            if num != local and num not in connected:
                connected.append(num)
    return connected


def _tail_lines(path: Path, limit: int = 50) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-limit:]


def _mesh_name_lookup() -> Dict[str, str]:
    """
    Build a map of node_id -> human name from any available source:
    - Fallback collected IDs (logs, messages)
    - Live --nodes output if reachable
    """
    names: Dict[str, str] = {}

    def _add_name(nid: str, name: str) -> None:
        if not nid:
            return
        names[nid] = name or nid
        if nid.startswith("!"):
            # Allow lookups with or without leading bang
            names.setdefault(nid.lstrip("!"), names[nid])

    try:
        for entry in _collect_mesh_ids_fallback():
            nid = entry.get("id")
            if nid:
                _add_name(nid, entry.get("name") or nid)
    except Exception:
        pass
    # Try live --nodes (TCP/serial) and include user.longName if present
    try:
        raw = _run_meshtastic(["--nodes"])
        if raw:
            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if parsed:
                for entry in parsed.get("nodes", []):
                    nid = entry.get("id") or entry.get("num") or entry.get("user", {}).get("id")
                    long_name = entry.get("longName") or entry.get("user", {}).get("longName")
                    short_name = entry.get("shortName") or entry.get("user", {}).get("shortName")
                    if nid:
                        nid_str = str(nid)
                        _add_name(nid_str, long_name or short_name or nid_str)
            else:
                for entry in _parse_nodes_table(raw):
                    nid = entry.get("id")
                    if not nid:
                        continue
                    name = entry.get("name") or str(nid)
                    _add_name(str(nid), name)
    except Exception:
        pass
    return names


def _latest_matching(lines: List[str], substring: str, limit: int = 10) -> List[str]:
    matched = [ln for ln in lines if substring in ln]
    return matched[-limit:]


def _append_queue_line(line: str) -> None:
    try:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE_FILE.open("a", encoding="utf-8") as f:
            f.write(line.strip() + "\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write queue: {e}")


def _load_nodes() -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    if not ALLMON3_INI.exists():
        return nodes
    parser = configparser.ConfigParser()
    parser.read(ALLMON3_INI)
    for section in parser.sections():
        if not section.isdigit():
            continue
        node_id = int(section)
        host = parser.get(section, "host", fallback="127.0.0.1").strip()
        user = parser.get(section, "user", fallback="").strip()
        password = parser.get(section, "pass", fallback="").strip()
        nodes.append({"id": node_id, "host": host, "user": user, "password": password})
    nodes.sort(key=lambda n: n["id"])
    return nodes


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _get_favorites() -> Dict[str, Any]:
    return _load_json(FAVORITES_PATH, {"nodes": {}, "modes": {}, "mesh": {}})


def _write_favorites(data: Dict[str, Any]) -> None:
    _save_json(FAVORITES_PATH, data)


def _get_state() -> Dict[str, Any]:
    return _load_json(STATE_PATH, {})


def _write_state(data: Dict[str, Any]) -> None:
    _save_json(STATE_PATH, data)


def _compute_aprs_passcode(callsign: str) -> int:
    # Standard APRS-IS passcode algorithm
    cs = callsign.split("-")[0].upper()
    hash_val = 0x73e2
    for i, ch in enumerate(cs):
        c = ord(ch)
        if i & 1:
            hash_val ^= c
        else:
            hash_val ^= (c << 8)
    return hash_val & 0x7fff


def _parse_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip().strip('"')
    return data


def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return (r_km * c) * 0.621371


def _geocode_zip(zip_code: str) -> Optional[Dict[str, float]]:
    """Lookup ZIP to lat/lon via zippopotam.us (no key required)."""
    if not zip_code:
        return None
    try:
        resp = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        places = data.get("places") or []
        if not places:
            return None
        place = places[0]
        return {"lat": float(place["latitude"]), "lon": float(place["longitude"])}
    except Exception:
        return None


def _get_aprs_config() -> Dict[str, Any]:
    state = _get_state().get("aprs", {})
    cfg: Dict[str, Any] = {
        "callsign": state.get("callsign") or os.getenv("APRS_CALLSIGN") or APRS_CALLSIGN,
        "watch": state.get("watch") or APRS_DEFAULT_WATCH,
        "zip": state.get("zip") or APRS_DEFAULT_ZIP,
        "radius_miles": float(state.get("radius_miles") or APRS_DEFAULT_RADIUS_MI),
        "target": state.get("target") or state.get("callsign") or "W4VDX-9",
    }
    geo = state.get("geo") or {}
    if geo.get("zip") == cfg["zip"]:
        cfg["lat"] = geo.get("lat")
        cfg["lon"] = geo.get("lon")
    else:
        cfg["lat"] = None
        cfg["lon"] = None
    return cfg


def _save_aprs_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    state = _get_state()
    aprs_state = state.get("aprs", {})
    target_val = cfg.get("target") or cfg.get("watch") or aprs_state.get("target") or "W4VDX-9"
    aprs_state.update({
        "callsign": cfg.get("callsign") or APRS_CALLSIGN,
        "watch": cfg.get("watch") or APRS_DEFAULT_WATCH,
        "zip": cfg.get("zip") or APRS_DEFAULT_ZIP,
        "radius_miles": cfg.get("radius_miles") or APRS_DEFAULT_RADIUS_MI,
        "target": target_val,
    })
    if cfg.get("lat") is not None and cfg.get("lon") is not None:
        aprs_state["geo"] = {"zip": aprs_state["zip"], "lat": cfg["lat"], "lon": cfg["lon"]}
    state["aprs"] = aprs_state
    _write_state(state)
    return aprs_state


def _ensure_aprs_geo(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if cfg.get("lat") is not None and cfg.get("lon") is not None:
        return cfg
    geo = _geocode_zip(cfg.get("zip") or APRS_DEFAULT_ZIP)
    if geo:
        cfg.update(geo)
        _save_aprs_config(cfg)
    return cfg


def _build_aprs_filter(cfg: Dict[str, Any]) -> str:
    watch = (cfg.get("watch") or APRS_DEFAULT_WATCH).upper()
    parts = [f"p/{watch}", "t/m"]
    if cfg.get("lat") is not None and cfg.get("lon") is not None:
        radius_km = round(float(cfg.get("radius_miles") or APRS_DEFAULT_RADIUS_MI) * 1.60934)
        parts.append(f"r/{cfg['lat']:.4f}/{cfg['lon']:.4f}/{radius_km}")
    return ",".join(parts)


def _update_aprs_env(cfg: Dict[str, Any]) -> Dict[str, Any]:
    env_defaults = _parse_env_file(APRS_ENV_FILE)
    cfg = _ensure_aprs_geo(dict(cfg))
    callsign = cfg.get("callsign") or APRS_CALLSIGN
    target = cfg.get("target") or cfg.get("watch") or callsign
    env: Dict[str, str] = {
        "APRS_CALLSIGN": callsign,
        "APRS_PASSCODE": str(_compute_aprs_passcode(callsign)),
        "APRS_SERVER": env_defaults.get("APRS_SERVER", "rotate.aprs.net"),
        "APRS_PORT": env_defaults.get("APRS_PORT", "14580"),
        "APRS_TARGET": target,
        "APRS_FILTER": _build_aprs_filter(cfg),
        "APRS_WATCH": (cfg.get("watch") or APRS_DEFAULT_WATCH).upper(),
        "APRS_ZIP": cfg.get("zip") or APRS_DEFAULT_ZIP,
        "APRS_RADIUS_MI": str(cfg.get("radius_miles") or APRS_DEFAULT_RADIUS_MI),
    }
    lines = [f"{k}={v}" for k, v in env.items()]
    APRS_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    APRS_ENV_FILE.write_text("# Auto-generated by susnet_api\n" + "\n".join(lines) + "\n")
    return cfg


def _aprs_line_matches(line: str, cfg: Dict[str, Any]) -> bool:
    watch = (cfg.get("watch") or "").lower()
    if watch and watch in line.lower():
        return True
    lat = cfg.get("lat")
    lon = cfg.get("lon")
    if lat is None or lon is None:
        return False
    match = re.search(r"([-+]?\d+\.\d+)[ ,]+([-+]?\d+\.\d+)", line)
    if not match:
        return False
    try:
        lat2 = float(match.group(1))
        lon2 = float(match.group(2))
    except Exception:
        return False
    if abs(lat2) > 90 or abs(lon2) > 180:
        return False
    dist = _distance_miles(lat, lon, lat2, lon2)
    return dist <= float(cfg.get("radius_miles") or APRS_DEFAULT_RADIUS_MI)


def _parse_aprs_line(line: str) -> Dict[str, Any]:
    """
    Best-effort APRS line parser to make the log more human-friendly.
    Expected shape: 'YYYY-MM-DD HH:MM:SS <body>'. Returns raw + parsed fields.
    """
    entry: Dict[str, Any] = {"raw": line, "text": line}
    ts_match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)$", line)
    body = line
    if ts_match:
        entry["timestamp"] = ts_match.group(1)
        body = ts_match.group(2)
        entry["text"] = body
    # Attempt to extract from/to/message from common patterns
    arrow_match = re.search(r"([A-Z0-9\-]+)[-]?>\s*([A-Z0-9\-]+)[: ]\s*(.*)", body)
    if arrow_match:
        entry["from"] = arrow_match.group(1)
        entry["to"] = arrow_match.group(2)
        entry["message"] = arrow_match.group(3)
    else:
        entry["message"] = body
    return entry


@app.get("/api/nodes")
def nodes():
    return {"ok": True, "nodes": _load_nodes()}


@app.post("/api/connect")
def connect(req: LinkRequest):
    local = req.localNode
    target = req.target
    mode_index = 2 if req.mode == "monitor" else 3
    out = _run_asterisk(f"rpt cmd {local} ilink {mode_index} {target}")
    return {"ok": True, "output": out}


@app.post("/api/disconnect")
def disconnect(req: LinkRequest):
    local = req.localNode
    target = req.target
    out = _run_asterisk(f"rpt cmd {local} ilink 1 {target}")
    return {"ok": True, "output": out}


@app.post("/api/disconnect-all")
def disconnect_all(req: LocalRequest):
    local = req.localNode
    out = _run_asterisk(f"rpt cmd {local} ilink 6")
    return {"ok": True, "output": out}


@app.post("/api/status")
def status(req: LocalRequest):
    local = req.localNode
    out = _run_asterisk(f"rpt nodes {local}")
    connected = _parse_connected(out, local)
    return {"ok": True, "connected": connected, "raw": out}


@app.post("/api/restart-asterisk")
def restart_asterisk():
    _run(["/bin/systemctl", "restart", "asterisk"])
    return {"ok": True}


@app.post("/api/reboot")
def reboot_host():
    _run(["/sbin/reboot"])
    return {"ok": True}


@app.post("/api/meshtastic/attach")
def meshtastic_attach():
    """Start the meshtastic-listener service to own the link."""
    _run(["/bin/systemctl", "start", "meshtastic-listener"])
    return {"ok": True}


@app.post("/api/meshtastic/detach")
def meshtastic_detach():
    """Stop the meshtastic-listener service to release the link for another client."""
    _run(["/bin/systemctl", "stop", "meshtastic-listener"])
    return {"ok": True}


@app.get("/api/favorites")
def favorites(scope: str, key: str):
    data = _get_favorites()
    bucket_name = "nodes" if scope == "node" else ("modes" if scope == "mode" else "mesh")
    bucket = data.get(bucket_name, {})
    return {"ok": True, "favorites": bucket.get(str(key), [])}


@app.post("/api/favorites")
def add_favorite(req: FavoriteRequest):
    data = _get_favorites()
    bucket_name = "nodes" if req.scope == "node" else ("modes" if req.scope == "mode" else "mesh")
    bucket = data.setdefault(bucket_name, {})
    items = bucket.setdefault(str(req.key), [])
    if not any(item.get("id") == req.id for item in items):
        items.append({"id": req.id, "label": req.label or req.id, "lat": req.lat, "lon": req.lon, "ts": time.time()})
    _write_favorites(data)
    return {"ok": True, "favorites": items}


@app.delete("/api/favorites")
def remove_favorite(req: DeleteFavoriteRequest):
    data = _get_favorites()
    bucket_name = "nodes" if req.scope == "node" else ("modes" if req.scope == "mode" else "mesh")
    bucket = data.setdefault(bucket_name, {})
    items = bucket.setdefault(str(req.key), [])
    items = [item for item in items if item.get("id") != req.id]
    bucket[str(req.key)] = items
    _write_favorites(data)
    return {"ok": True, "favorites": items}


@app.get("/api/mode/modes")
def mode_list():
    if not MODE_ALIAS_FILE.exists():
        return {"ok": True, "modes": []}
    import yaml

    raw = yaml.safe_load(MODE_ALIAS_FILE.read_text()) or {}
    modes = raw.get("modes", [])
    parsed = []
    for entry in modes:
        # entry like {'DMR': {'talkgroups': [...]}}
        if not isinstance(entry, dict):
            continue
        name, payload = next(iter(entry.items()))
        tgs = payload.get("talkgroups", []) if isinstance(payload, dict) else []
        parsed.append({"name": name, "talkgroups": tgs})
    return {"ok": True, "modes": parsed}


@app.post("/api/mode/select")
def mode_select(req: ModeSelectRequest):
    mode = req.mode
    tgid = req.tgid
    # Switch mode
    try:
        resp = requests.get(f"{MODE_SWITCHER_URL}/mode/{mode}", timeout=5)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mode switch failed: {e}")

    if tgid:
        try:
            resp2 = requests.get(f"{MODE_SWITCHER_URL}/tune/{tgid}", timeout=5)
            resp2.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Talkgroup tune failed: {e}")

    state = _get_state()
    state["mode"] = {"mode": mode, "tgid": tgid, "ts": time.time()}
    _write_state(state)
    return {"ok": True, "mode": mode, "tgid": tgid}


@app.get("/api/mode/status")
def mode_status():
    state = _get_state().get("mode", {})
    return {"ok": True, "mode": state.get("mode"), "tgid": state.get("tgid"), "ts": state.get("ts")}


@app.get("/api/meshtastic/messages")
def meshtastic_messages():
    items: List[Dict[str, Any]] = []
    name_map = _mesh_name_lookup()
    channel_map: Dict[int, str] = {}
    try:
        for entry in MESHTASTIC_CHANNELS:
            if isinstance(entry, dict) and entry.get("index") is not None:
                idx = _safe_int(entry.get("index"))
                if idx is not None and entry.get("name"):
                    channel_map[idx] = entry.get("name")
    except Exception:
        pass
    if MESHTASTIC_JSON.exists():
        try:
            data = json.loads(MESHTASTIC_JSON.read_text())
            for entry in data[-200:]:
                if not isinstance(entry, dict):
                    continue
                ts = entry.get("timestamp")
                from_id = entry.get("from_id") or entry.get("fromId")
                to_id = entry.get("to_id") or entry.get("toId")
                text = entry.get("text") or ""
                ch_idx = entry.get("channelIndex")
                try:
                    ch_idx = int(ch_idx) if ch_idx is not None else None
                except Exception:
                    ch_idx = None
                channel = entry.get("channel") or channel_map.get(ch_idx, "Primary")
                direct = bool(to_id and to_id not in ("^all", "^local"))
                items.append({
                    "timestamp": ts,
                    "from": from_id,
                    "from_name": name_map.get(from_id, from_id),
                    "to": to_id,
                    "to_name": name_map.get(to_id, to_id),
                    "text": text,
                    "channel": channel,
                    "channelIndex": ch_idx,
                    "direct": direct,
                })
        except Exception:
            items = []
    lines = _tail_lines(MESHTASTIC_MESSAGES, 200)
    return {"ok": True, "lines": lines[::-1], "items": items[::-1] if items else []}


@app.get("/api/meshtastic/telemetry")
def meshtastic_telemetry():
    lines = _tail_lines(MESHTASTIC_LOG, 200)
    telem = _latest_matching(lines, "[Telemetry]", 50)
    return {"ok": True, "lines": telem[::-1]}


@app.post("/api/meshtastic/send")
def meshtastic_send(req: SendRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message required")
    payload: Dict[str, Any] = {"text": text}
    if req.dest:
        payload["dest"] = req.dest.strip()
    # Map channel_name to index if possible using cached channels
    ch_name = (req.channel_name or req.channel or "").strip()
    ch_idx = None
    if req.channel_index is not None:
        ch_idx = _safe_int(req.channel_index)
    if ch_idx is None and ch_name:
        # if the caller provided a numeric-looking channel name, honor it
        ch_idx = _safe_int(ch_name)
    if ch_idx is None and ch_name:
        ch_idx = _channel_index_from_cache(ch_name)
    if ch_idx is not None:
        payload["channelIndex"] = ch_idx
    if ch_name:
        payload["channelName"] = ch_name
        payload["channel"] = ch_name
    try:
        _append_queue_line(f"SENDJSON:{json.dumps(payload)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"queue write failed: {e}")
    return {"ok": True}


@app.post("/api/meshtastic/command")
def meshtastic_command(req: CommandRequest):
    cmd = req.command.strip().upper()
    allowed = {"STATUS", "INFO", "MUTE", "UNMUTE", "LOUD", "QUIET"}
    if cmd not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported command: {cmd}")
    _append_queue_line(f"CMD:{cmd}")
    return {"ok": True}


@app.get("/api/meshtastic/topology")
def meshtastic_topology():
    nodes: List[Dict[str, Any]] = []
    channels: List[str] = []
    channel_details: List[Dict[str, Any]] = []
    activity = _collect_node_activity()
    favs = _get_favorites().get("mesh", {}).get("global", [])
    fav_ids = {item.get("id") for item in favs if item.get("id")}
    raw_nodes = _run_meshtastic(["--nodes"])
    if raw_nodes:
        try:
            parsed = json.loads(raw_nodes)
            for entry in parsed.get("nodes", []):
                nid = entry.get("num") or entry.get("id") or entry.get("user", {}).get("id")
                long_name = entry.get("longName") or entry.get("user", {}).get("longName")
                short_name = entry.get("shortName") or entry.get("user", {}).get("shortName")
                if nid:
                    nid_str = str(nid)
                    meta = activity.get(nid_str) or activity.get(f"!{nid_str}")
                    last = meta["last"] if meta else 0
                    age_hours = (time.time() - last) / 3600 if last else None
                    nodes.append({
                        "id": nid_str,
                        "name": long_name or short_name or str(nid_str),
                        "last_seen": last,
                        "age_hours": age_hours,
                        "stale": bool(age_hours and age_hours >= 36),
                        "via_mqtt": bool(meta and meta.get("via_mqtt")),
                        "favorite": nid_str in fav_ids,
                    })
        except Exception:
            # non-JSON; try to parse the table output
            parsed_table = _parse_nodes_table(raw_nodes)
            for entry in parsed_table:
                nid_str = entry.get("id")
                meta = activity.get(nid_str) or activity.get(f"!{nid_str}") if nid_str else None
                last = meta["last"] if meta else 0
                age_hours = (time.time() - last) / 3600 if last else None
                nodes.append({
                    "id": nid_str,
                    "name": entry.get("name") or nid_str,
                    "last_seen": last,
                    "age_hours": age_hours,
                    "stale": bool(age_hours and age_hours >= 36),
                    "via_mqtt": bool(meta and meta.get("via_mqtt")),
                    "favorite": bool(nid_str and nid_str in fav_ids),
                })
    if not nodes:
        nodes = _collect_mesh_ids_fallback()
        # enrich fallback with activity
        for n in nodes:
            meta = activity.get(n["id"])
            if meta:
                last = meta["last"]
                age_hours = (time.time() - last) / 3600 if last else None
                n.update({
                    "last_seen": last,
                    "age_hours": age_hours,
                    "stale": bool(age_hours and age_hours >= 36),
                    "via_mqtt": bool(meta.get("via_mqtt")),
                    "favorite": n["id"] in fav_ids,
                })
    raw_info = _run_meshtastic(["--info"])
    if raw_info:
        raw_names = _extract_channel_names(raw_info)
        channel_details = _parse_channel_details(raw_info, raw_names)
        channels = [c.get("name") for c in channel_details if isinstance(c, dict) and c.get("name")] or raw_names
    # cache channel list for name->index mapping on send
    try:
        global MESHTASTIC_CHANNELS
        MESHTASTIC_CHANNELS = channel_details or [{"index": idx, "name": name} for idx, name in enumerate(channels)]
    except Exception:
        pass
    return {"ok": True, "nodes": nodes, "channels": channels, "channel_details": channel_details}


@app.get("/api/aprs/messages")
def aprs_messages():
    cfg = _ensure_aprs_geo(_get_aprs_config())
    lines = _tail_lines(APRS_LOG, 400)
    filtered = [ln for ln in reversed(lines) if _aprs_line_matches(ln, cfg)]
    trimmed = filtered[:200]
    entries = [_parse_aprs_line(ln) for ln in trimmed]
    return {"ok": True, "lines": trimmed, "entries": entries, "order": "newest_first", "config": cfg}


@app.get("/api/aprs/config")
def aprs_config():
    cfg = _ensure_aprs_geo(_get_aprs_config())
    cfg["filter"] = _build_aprs_filter(cfg)
    return {"ok": True, "config": cfg}


@app.post("/api/aprs/config")
def aprs_config_update(req: AprsConfigRequest):
    zip_code = req.zip.strip()
    if not re.match(r"^\d{3,10}$", zip_code):
        raise HTTPException(status_code=400, detail="ZIP must be numeric")
    watch = req.watch.strip().upper()
    cfg = {
        "zip": zip_code,
        "radius_miles": float(req.radius_miles),
        "watch": watch,
        "target": (req.target or "").strip() or None,
        "callsign": (req.callsign or "").strip() or None,
    }
    geo = _geocode_zip(zip_code)
    if not geo:
        raise HTTPException(status_code=400, detail="Failed to geocode ZIP")
    cfg.update(geo)
    cfg_saved = _save_aprs_config(cfg)
    cfg_saved.update(geo)
    cfg_saved["filter"] = _build_aprs_filter(cfg_saved)
    _update_aprs_env(cfg_saved)
    subprocess.run(["/bin/systemctl", "restart", "meshtastic-aprs.service"], check=False)
    return {"ok": True, "config": cfg_saved}


@app.post("/api/aprs/send")
def aprs_send(req: SendRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message required")
    tocall = (req.dest or "APZXXX").upper()
    cfg = _get_aprs_config()
    callsign = cfg.get("callsign") or APRS_CALLSIGN
    passcode = _compute_aprs_passcode(callsign)
    import aprslib

    try:
        client = aprslib.IS(callsign, passwd=passcode, port=14580, host="rotate.aprs2.net")
        client.connect()
        # Send a basic APRS message packet to the destination
        payload = f"{callsign}>APRS::{tocall:<9}:{text}"
        client.sendall(payload)
        client.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"APRS send failed: {e}")
    return {"ok": True}


@app.get("/api/map")
def map_points():
    favs = _get_favorites()
    points = []
    for node_id, items in favs.get("nodes", {}).items():
        for item in items:
            if item.get("lat") is None or item.get("lon") is None:
                continue
            points.append({
                "source": "favorite",
                "subtype": "node",
                "ref": node_id,
                "id": item.get("id"),
                "label": item.get("label"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "ts": item.get("ts"),
            })
    # Try to parse APRS log for coords
    for line in _tail_lines(APRS_LOG, 200):
        match = re.search(r"([-+]?\d+\.\d+)[ ,]+([-+]?\d+\.\d+)", line)
        if match:
            points.append({
                "source": "aprs",
                "id": line[:20].strip(),
                "label": line.strip(),
                "lat": float(match.group(1)),
                "lon": float(match.group(2)),
                "ts": time.time(),
            })
    return {"ok": True, "points": points}


@app.get("/api/services")
def services():
    units = [
        "asterisk",
        "susnet-api",
        "meshtastic-listener",
        "meshtastic-aprs",
        "dvswitch_mode_switcher",
        "MMDVM_Bridge",
        "Analog_Bridge",
    ]
    data = {}
    for unit in units:
        try:
            out = _run(["/bin/systemctl", "is-active", unit])
            data[unit] = out.strip()
        except HTTPException as e:
            data[unit] = f"error: {e.detail}"
    return {"ok": True, "services": data}


@app.get("/api/health")
def health():
    return {"ok": True, "ts": time.time(), "version": VERSION}


@app.get("/api/tickets")
def list_tickets(status: str = "open"):
    status = status.lower()
    if status not in {"open", "closed", "all"}:
        raise HTTPException(status_code=400, detail="status must be open|closed|all")
    tickets = _collect_tickets(status)
    return {"ok": True, "tickets": tickets}


@app.post("/api/tickets")
def create_ticket(req: TicketCreateRequest):
    _ensure_trouble_dirs()
    ticket_id = _next_ticket_id()
    now = datetime.utcnow().date().isoformat()
    title = _sanitize_line(req.title)
    subsystem = _sanitize_line(req.subsystem or "unspecified")
    severity = _sanitize_line(req.severity or "medium")
    description = req.description.strip()
    body = "\n".join([
        f"# {ticket_id} - {title}",
        "",
        f"- Date opened: {now}",
        f"- Date closed:",
        f"- Subsystem: {subsystem}",
        f"- Severity: {severity}",
        f"- Status: open",
        "",
        "## Summary",
        description,
        "",
        "## Resolution",
        "(pending)",
        "",
        "## Follow-up",
        "- (add next steps here)",
        "",
    ])
    path = TROUBLE_OPEN / f"{ticket_id}.md"
    path.write_text(body)
    _update_master_from_fs()
    try:
        _speak_tts(f"Support ticket {ticket_id} created. Severity {severity}. Subsystem {subsystem}.")
    except Exception:
        pass
    return {"ok": True, "id": ticket_id}


@app.post("/api/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, req: TicketCloseRequest):
    ticket_id = ticket_id if ticket_id.startswith("TKT-") else f"TKT-{ticket_id}"
    src = TROUBLE_OPEN / f"{ticket_id}.md"
    if not src.exists():
        raise HTTPException(status_code=404, detail="ticket not found")
    lines = src.read_text().splitlines()
    today = datetime.utcnow().date().isoformat()
    out: List[str] = []
    for line in lines:
        if line.startswith("- Date closed:"):
            out.append(f"- Date closed: {today}")
        elif line.startswith("- Status:"):
            out.append("- Status: closed")
        else:
            out.append(line)
    out.append("")
    out.append(f"## Closure ({today})")
    if req.resolution:
        out.append(f"Resolution: {_sanitize_line(req.resolution)}")
    if req.followup:
        out.append(f"Follow-up: {_sanitize_line(req.followup)}")
    out.append("")
    src.write_text("\n".join(out))
    dst = TROUBLE_CLOSED / src.name
    src.replace(dst)
    _update_master_from_fs()
    return {"ok": True, "id": ticket_id}


@app.post("/api/tts")
def speak_tts(req: TtsRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    _speak_tts(text, req.node)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("susnet_api:app", host="0.0.0.0", port=8088, reload=False)
