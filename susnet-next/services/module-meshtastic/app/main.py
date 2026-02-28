from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import meshtastic
import meshtastic.serial_interface  # type: ignore
import meshtastic.tcp_interface  # type: ignore
from fastapi import Body, FastAPI, Query
from fastapi.responses import JSONResponse
from meshtastic.protobuf import channel_pb2
from pubsub import pub  # type: ignore

try:
    import paho.mqtt.client as mqtt  # type: ignore
except Exception:
    mqtt = None


# --------------------------- config ---------------------------

DATA_DIR = Path(os.getenv("MESH_DATA_DIR", "/data"))
MSG_FILE = DATA_DIR / "messages.json"
TEL_FILE = DATA_DIR / "telemetry.json"
NODE_FILE = DATA_DIR / "nodes.json"
MQTT_CFG_FILE = DATA_DIR / "mqtt_config.json"
MQTT_MSG_FILE = DATA_DIR / "mqtt_messages.json"

MAX_ITEMS = int(os.getenv("MESH_MAX_ITEMS", "500"))
MESHTASTIC_HOST = os.getenv("MESHTASTIC_HOST")
MESHTASTIC_TCP_PORT = int(os.getenv("MESHTASTIC_TCP_PORT", "4403"))
MESHTASTIC_SERIAL_PORT = os.getenv("MESHTASTIC_SERIAL_PORT", "/dev/ttyUSB0")
MESHTASTIC_ADMIN_ENABLED = os.getenv("MESHTASTIC_ADMIN_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# When false (default), redact sensitive material (PSKs, URLs with keys, passwords) from CLI outputs.
# This prevents accidental key disclosure via API/UI.
MESHTASTIC_SENSITIVE_OUTPUT_ENABLED = os.getenv("MESHTASTIC_SENSITIVE_OUTPUT_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
CLI_TIMEOUT = int(os.getenv("MESHTASTIC_CLI_TIMEOUT", "45"))
NODE_SNAPSHOT_INTERVAL_SECONDS = float(os.getenv("MESH_NODE_SNAPSHOT_SECONDS", "15"))

MQTT_DEFAULT_HOST = os.getenv("MESH_MQTT_HOST", "host.docker.internal")
MQTT_DEFAULT_PORT = int(os.getenv("MESH_MQTT_PORT", "1883"))
MQTT_DEFAULT_USER = os.getenv("MESH_MQTT_USER", "")
MQTT_DEFAULT_PASS = os.getenv("MESH_MQTT_PASS", "")
MQTT_DEFAULT_TLS = os.getenv("MESH_MQTT_TLS", "false").lower() in ("1", "true", "yes", "on")
MQTT_DEFAULT_QOS = int(os.getenv("MESH_MQTT_QOS", "0"))
MQTT_DEFAULT_AUTOCONNECT = os.getenv("MESH_MQTT_AUTOCONNECT", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MQTT_DEFAULT_DOWNLINK_TOPIC = os.getenv("MESH_MQTT_DOWNLINK_TOPIC", "msh/downlink")

app = FastAPI(title="susnet-module-meshtastic", version="0.3.0")


# --------------------------- runtime state ---------------------------

_lock = threading.RLock()
_mqtt_lock = threading.RLock()

_messages: List[Dict[str, Any]] = []
_telemetry: List[str] = []
_nodes: Dict[str, Dict[str, Any]] = {}

_interface: Optional[Any] = None
_last_error: Optional[str] = None
_connected_via: Optional[str] = None
_stop_event = threading.Event()
_subscribed = False
_suspend_connect = threading.Event()

_mqtt_cfg: Dict[str, Any] = {}
_mqtt_client: Optional[Any] = None
_mqtt_connected = False
_mqtt_last_error: Optional[str] = None
_mqtt_subscriptions: Set[str] = set()
_mqtt_messages: List[Dict[str, Any]] = []
_mqtt_seen_hashes: Set[str] = set()
_mqtt_seen_order: List[str] = []


# --------------------------- persistence ---------------------------


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _trim_list(items: List[Any], limit: int = MAX_ITEMS) -> None:
    if len(items) > limit:
        del items[:-limit]


def _save_messages() -> None:
    _save_json(MSG_FILE, _messages)


def _save_telemetry() -> None:
    _save_json(TEL_FILE, _telemetry)


def _save_nodes() -> None:
    _save_json(NODE_FILE, list(_nodes.values()))


def _save_mqtt_cfg() -> None:
    _save_json(MQTT_CFG_FILE, _mqtt_cfg)


def _save_mqtt_messages() -> None:
    _save_json(MQTT_MSG_FILE, _mqtt_messages)


# --------------------------- helpers ---------------------------


def _wrap_ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data, "errors": []}


def _wrap_err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "data": None, "errors": [msg]}


def _now_ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(msg: str) -> None:
    print(f"[meshtastic] {msg}", flush=True)


def _normalize_node_id(node_id: Any) -> str:
    if node_id is None:
        return ""
    s = str(node_id).strip()
    if not s:
        return ""
    if s.startswith("!"):
        return s.lower()
    if s.startswith("0x"):
        try:
            return f"!{int(s, 16):08x}"
        except Exception:
            return f"!{s[2:].lower()}"
    if len(s) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in s):
        return f"!{s.lower()}"
    return s


def _display_name(short_name: Optional[str], long_name: Optional[str], node_id: Optional[str]) -> str:
    short = (short_name or "").strip() or (_normalize_node_id(node_id) or "unknown")
    longn = (long_name or "").strip() or short
    return f"{short}>{longn}"


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _sanitize_topic(topic: str) -> str:
    return (topic or "").strip()


def _redact_text_secrets(text: str) -> str:
    """Best-effort redaction for CLI/stdout content.

    We keep CLI parity while avoiding accidental key disclosure (PSKs, passwords).
    """
    if MESHTASTIC_SENSITIVE_OUTPUT_ENABLED:
        return text
    if not text:
        return text

    import re

    out = text

    # Common YAML/INI-ish forms.
    # Note: `channel_url` contains a full shareable channel URL (includes keys) and must be treated as sensitive.
    for key in (
        "psk",
        "password",
        "pass",
        "passphrase",
        "api_key",
        "token",
        "secret",
        "privateKey",
        "fixedPin",
        "channel_url",
        "channelUrl",
    ):
        out = re.sub(rf"(?im)^(\s*{key}\s*:\s*).*$", r"\1<redacted>", out)  # YAML
        out = re.sub(rf"(?im)^(\s*{key}\s*=\s*).*$", r"\1<redacted>", out)  # INI

    # URLs often include PSKs (e.g. `psk=...`).
    out = re.sub(r"(?i)(psk=)[^&\s]+", r"\1<redacted>", out)
    # Also redact any explicit `channel_url` style URLs (Meshtastic "e/#..." URLs embed keys).
    out = re.sub(r"(?im)^(\s*channel_url\s*:\s*).*$", r"\1<redacted>", out)
    out = re.sub(r'(?i)("channel_url"\\s*:\\s*)"[^"]+"', r'\\1"<redacted>"', out)
    out = re.sub(r'(?i)("channelUrl"\\s*:\\s*)"[^"]+"', r'\\1"<redacted>"', out)
    return out


def _normalize_command_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Allow both `{...}` and `{args:{...}, ...}` request bodies."""
    if not isinstance(payload, dict):
        return {}
    args = payload.get("args")
    if isinstance(args, dict):
        merged = dict(args)
        for k, v in payload.items():
            if k != "args":
                merged[k] = v
        return merged
    return payload


def _ensure_channels_loaded(interface: Any) -> None:
    try:
        node = getattr(interface, "localNode", None)
        if not node:
            return
        if getattr(node, "channels", None):
            return
        node.requestChannels()
        node.waitForConfig(attribute="channels")
    except Exception:
        return


def _extract_user_fields(node_obj: Any) -> Tuple[str, str, Optional[int], str]:
    short_name = ""
    long_name = ""
    node_num: Optional[int] = None
    node_id = ""

    try:
        if isinstance(node_obj, dict):
            user = node_obj.get("user") or {}
            short_name = str(user.get("shortName") or node_obj.get("shortName") or "").strip()
            long_name = str(user.get("longName") or node_obj.get("longName") or "").strip()
            node_num = _coerce_int(node_obj.get("num") or node_obj.get("nodeNum"))
            node_id = str(user.get("id") or node_obj.get("id") or "").strip()
        else:
            user = getattr(node_obj, "user", None)
            if user is not None:
                short_name = str(getattr(user, "shortName", "") or "").strip()
                long_name = str(getattr(user, "longName", "") or "").strip()
                node_id = str(getattr(user, "id", "") or "").strip()
            node_num = _coerce_int(getattr(node_obj, "num", None) or getattr(node_obj, "nodeNum", None))
    except Exception:
        pass

    return short_name, long_name, node_num, node_id


def _upsert_node(
    node_id: Any,
    short_name: Optional[str] = None,
    long_name: Optional[str] = None,
    node_num: Optional[int] = None,
    last_heard: Optional[str] = None,
) -> Dict[str, Any]:
    nid = _normalize_node_id(node_id)
    if not nid:
        nid = "unknown"

    with _lock:
        existing = _nodes.get(nid, {})
        short = (short_name or existing.get("shortName") or "").strip()
        longn = (long_name or existing.get("longName") or "").strip()
        if not short:
            short = nid
        if not longn:
            longn = short

        # Preserve prior last_heard when no explicit update is provided.
        # This avoids rewriting every node record on each snapshot/poll cycle.
        effective_last_heard = last_heard if last_heard is not None else existing.get("last_heard") or _now_ts()
        rec = {
            "id": nid,
            "nodeNum": node_num if node_num is not None else existing.get("nodeNum"),
            "shortName": short,
            "longName": longn,
            "displayName": _display_name(short, longn, nid),
            "first_heard": existing.get("first_heard") or _now_ts(),
            "last_heard": effective_last_heard,
        }

        if rec != existing:
            _nodes[nid] = rec
            _save_nodes()
            return rec
        return existing


def _find_node(node_id: Any) -> Optional[Dict[str, Any]]:
    nid = _normalize_node_id(node_id)
    if not nid:
        return None
    with _lock:
        if nid in _nodes:
            return _nodes[nid]
        # allow lookup by non-bang id and by decimal node number string
        for rec in _nodes.values():
            if rec.get("id") == nid:
                return rec
            node_num = rec.get("nodeNum")
            if node_num is not None and str(node_num) == str(node_id):
                return rec
    return None


def _node_display(node_id: Any) -> str:
    rec = _find_node(node_id)
    if rec:
        return rec.get("displayName") or _display_name(rec.get("shortName"), rec.get("longName"), rec.get("id"))
    nid = _normalize_node_id(node_id)
    return _display_name(nid, nid, nid)


def _snapshot_nodes(interface: Any) -> None:
    try:
        nodes = getattr(interface, "nodes", {}) or {}
    except Exception:
        nodes = {}

    for key, node_obj in (nodes.items() if isinstance(nodes, dict) else []):
        short_name, long_name, node_num, node_id = _extract_user_fields(node_obj)
        nid = node_id or str(key)
        _upsert_node(nid, short_name=short_name, long_name=long_name, node_num=node_num)


def _append_message(item: Dict[str, Any]) -> None:
    with _lock:
        _messages.append(item)
        _trim_list(_messages)
        _save_messages()


def _append_telemetry(line: str) -> None:
    with _lock:
        _telemetry.append(line)
        _trim_list(_telemetry)
        _save_telemetry()


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


def _resolve_channel_label(interface: Any, channel_name: Optional[str], channel_index: Optional[int]) -> str:
    label = channel_name
    try:
        _ensure_channels_loaded(interface)
        node = getattr(interface, "localNode", None)
        if node and getattr(node, "channels", None) and channel_index is not None:
            ch = node.getChannelByChannelIndex(channel_index)
            if ch and ch.role != channel_pb2.Channel.Role.DISABLED:
                label = getattr(ch.settings, "name", label) or label
        if not label and channel_index is not None:
            label = f"#{channel_index}"
    except Exception:
        pass
    return label or "Primary"


def _list_channels(interface: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        _ensure_channels_loaded(interface)
        node = getattr(interface, "localNode", None)
        channels = getattr(node, "channels", []) if node else []
        for ch in channels or []:
            try:
                role = getattr(ch, "role", None)
                role_name = str(role)
                if role == channel_pb2.Channel.Role.DISABLED:
                    continue
                idx = _coerce_int(getattr(ch, "index", None))
                settings = getattr(ch, "settings", None)
                name = str(getattr(settings, "name", "") or "").strip() or (
                    "Primary" if idx == 0 else f"Channel {idx}"
                )
                # Never return PSKs/keys via API.
                psk_present = False
                try:
                    psk = getattr(settings, "psk", None) if settings else None
                    psk_present = bool(psk) and str(psk) not in ("b''", "None", "")
                except Exception:
                    psk_present = False
                out.append(
                    {
                        "index": idx,
                        "name": name,
                        "role": role_name,
                        "psk_present": psk_present,
                    }
                )
            except Exception:
                continue
    except Exception:
        pass

    if not out:
        out.append({"index": 0, "name": "Primary", "role": "PRIMARY"})
    return sorted(out, key=lambda i: i.get("index", 0))


def _resolve_send_channel(interface: Any, channel_name: Optional[str], channel_index: Optional[int]) -> Tuple[Optional[int], str]:
    resolved_idx: Optional[int] = None
    label = channel_name

    try:
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
    except Exception:
        pass

    if resolved_idx is None and isinstance(channel_index, int):
        resolved_idx = channel_index
    if not label:
        label = f"#{resolved_idx}" if resolved_idx is not None else "Primary"
    return resolved_idx, label


# --------------------------- MQTT manager ---------------------------


def _default_mqtt_cfg() -> Dict[str, Any]:
    return {
        "enabled": MQTT_DEFAULT_AUTOCONNECT,
        "host": MQTT_DEFAULT_HOST,
        "port": MQTT_DEFAULT_PORT,
        "username": MQTT_DEFAULT_USER,
        "password": MQTT_DEFAULT_PASS,
        "tls": MQTT_DEFAULT_TLS,
        "client_id": f"susnet-mesh-{socket.gethostname()}",
        "keepalive": 60,
        "qos": MQTT_DEFAULT_QOS,
        "topics": ["msh/#"],
        "downlink_topic": MQTT_DEFAULT_DOWNLINK_TOPIC,
    }


def _mqtt_redacted_cfg() -> Dict[str, Any]:
    with _mqtt_lock:
        out = dict(_mqtt_cfg)
    out["password"] = ""
    out["password_set"] = bool(_mqtt_cfg.get("password"))
    return out


def _mqtt_add_message(topic: str, payload: bytes, qos: int, retain: bool) -> None:
    global _mqtt_messages

    ts = _now_ts()
    seen_hash = hashlib.sha1(topic.encode("utf-8") + b"\x00" + payload).hexdigest()
    payload_text = ""
    try:
        payload_text = payload.decode("utf-8")
    except Exception:
        payload_text = ""

    with _mqtt_lock:
        deduped = seen_hash in _mqtt_seen_hashes
        if not deduped:
            _mqtt_seen_hashes.add(seen_hash)
            _mqtt_seen_order.append(seen_hash)
            if len(_mqtt_seen_order) > (MAX_ITEMS * 4):
                old = _mqtt_seen_order.pop(0)
                _mqtt_seen_hashes.discard(old)

        entry = {
            "ts": ts,
            "topic": topic,
            "qos": qos,
            "retain": retain,
            "seen_hash": seen_hash,
            "deduped": deduped,
            "payload_text": payload_text,
            "payload_b64": base64.b64encode(payload).decode("ascii"),
        }
        _mqtt_messages.append(entry)
        _trim_list(_mqtt_messages)
        _save_mqtt_messages()


def _mqtt_on_connect(client, userdata, flags, rc, properties=None):  # type: ignore
    global _mqtt_connected, _mqtt_last_error
    with _mqtt_lock:
        _mqtt_connected = rc == 0
        if rc != 0:
            _mqtt_last_error = f"connect failed rc={rc}"
            return
        _mqtt_last_error = None
        topics = _mqtt_cfg.get("topics") or []
        qos = int(_mqtt_cfg.get("qos", 0) or 0)
        for topic in topics:
            t = _sanitize_topic(str(topic))
            if not t:
                continue
            try:
                client.subscribe(t, qos=qos)
                _mqtt_subscriptions.add(t)
            except Exception as exc:
                _mqtt_last_error = f"subscribe {t} failed: {exc}"


def _mqtt_on_disconnect(client, userdata, rc, properties=None):  # type: ignore
    global _mqtt_connected
    with _mqtt_lock:
        _mqtt_connected = False


def _mqtt_on_message(client, userdata, msg):  # type: ignore
    payload = msg.payload or b""
    _mqtt_add_message(msg.topic, payload, int(msg.qos), bool(msg.retain))


def _mqtt_build_client() -> Tuple[Optional[Any], Optional[str]]:
    if mqtt is None:
        return None, "not_enabled:mqtt_client_missing"

    cfg = dict(_mqtt_cfg)
    client_id = str(cfg.get("client_id") or f"susnet-mesh-{socket.gethostname()}")
    try:
        client = mqtt.Client(client_id=client_id)  # type: ignore[arg-type]
    except Exception:
        client = mqtt.Client()  # type: ignore[call-arg]

    username = str(cfg.get("username") or "")
    password = str(cfg.get("password") or "")
    if username:
        client.username_pw_set(username, password)

    if bool(cfg.get("tls")):
        client.tls_set()

    client.on_connect = _mqtt_on_connect
    client.on_disconnect = _mqtt_on_disconnect
    client.on_message = _mqtt_on_message
    return client, None


def _mqtt_disconnect_internal() -> Dict[str, Any]:
    global _mqtt_client, _mqtt_connected
    with _mqtt_lock:
        client = _mqtt_client
        _mqtt_client = None
        _mqtt_connected = False
        _mqtt_subscriptions.clear()
    if client is None:
        return _wrap_ok({"connected": False})
    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass
    return _wrap_ok({"connected": False})


def _mqtt_connect_internal() -> Dict[str, Any]:
    global _mqtt_client, _mqtt_last_error

    with _mqtt_lock:
        cfg = dict(_mqtt_cfg)

    client, err = _mqtt_build_client()
    if err:
        _mqtt_last_error = err
        return _wrap_err(err)

    host = str(cfg.get("host") or MQTT_DEFAULT_HOST)
    port = int(cfg.get("port") or MQTT_DEFAULT_PORT)
    keepalive = int(cfg.get("keepalive") or 60)

    _mqtt_disconnect_internal()

    try:
        client.connect_async(host, port=port, keepalive=keepalive)
        client.loop_start()
    except Exception as exc:
        _mqtt_last_error = str(exc)
        return _wrap_err(f"mqtt connect failed: {exc}")

    with _mqtt_lock:
        _mqtt_client = client

    time.sleep(0.2)
    return _wrap_ok(
        {
            "connecting": True,
            "host": host,
            "port": port,
            "client_id": cfg.get("client_id"),
        }
    )


def _mqtt_publish(topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> Dict[str, Any]:
    with _mqtt_lock:
        client = _mqtt_client
        connected = _mqtt_connected

    if client is None:
        return _wrap_err("mqtt not initialized")
    if not connected:
        return _wrap_err("mqtt not connected")

    try:
        result = client.publish(topic, payload=payload, qos=qos, retain=retain)
        rc = int(getattr(result, "rc", 0))
        if rc != 0:
            return _wrap_err(f"mqtt publish rc={rc}")
    except Exception as exc:
        return _wrap_err(f"mqtt publish failed: {exc}")

    return _wrap_ok(
        {
            "published": True,
            "topic": topic,
            "qos": qos,
            "retain": retain,
            "size": len(payload),
        }
    )


def _mqtt_status_data() -> Dict[str, Any]:
    with _mqtt_lock:
        return {
            "connected": _mqtt_connected,
            "last_error": _mqtt_last_error,
            "subscriptions": sorted(_mqtt_subscriptions),
            "messages_count": len(_mqtt_messages),
            "config": _mqtt_redacted_cfg(),
        }


# --------------------------- meshtastic callbacks ---------------------------


def on_receive(packet: Dict[str, Any], interface) -> None:  # type: ignore
    decoded = packet.get("decoded", {}) or {}
    portnum = decoded.get("portnum")

    from_id = packet.get("fromId") or packet.get("from") or "unknown"
    to_id = packet.get("toId") or packet.get("to")
    rx_time = packet.get("rxTime")

    _snapshot_nodes(interface)
    _upsert_node(from_id, last_heard=_now_ts())
    if to_id:
        _upsert_node(to_id, last_heard=_now_ts())

    sender = _find_node(from_id) or _upsert_node(from_id)
    recipient = _find_node(to_id) if to_id else None

    if portnum == "TELEMETRY_APP":
        telemetry = decoded.get("telemetry", {}) or {}
        metrics = telemetry.get("deviceMetrics", {}) or {}
        battery = metrics.get("batteryLevel")
        voltage = metrics.get("voltage")
        uptime = metrics.get("uptimeSeconds")
        if isinstance(uptime, (int, float)):
            minutes = uptime / 60.0
            hours = minutes / 60.0
            uptime_str = f"{minutes:.1f} min (~{hours:.2f} h)"
        else:
            uptime_str = "unknown"
        display = sender.get("displayName") if sender else _node_display(from_id)
        line = (
            f"{_now_ts()} [Telemetry] Node {display}: battery {battery}% ({voltage} V), "
            f"up for {uptime_str}"
        )
        _append_telemetry(line)
        return

    if portnum != "TEXT_MESSAGE_APP":
        return

    text = decoded.get("text")
    if text is None:
        payload = decoded.get("payload", {}) or {}
        text = payload.get("text")
    if text is None:
        return

    channel_name = _extract_channel(packet, decoded)
    channel_index = _extract_channel_index(packet, decoded)
    channel_label = _resolve_channel_label(interface, channel_name, channel_index)

    is_dm = bool(to_id and to_id not in ("^all", "^local"))

    msg_item = {
        "time": _now_ts(),
        "rx_time": rx_time,
        "from_id": _normalize_node_id(from_id) or str(from_id),
        "to_id": _normalize_node_id(to_id) if to_id else "^all",
        "sender_shortName": sender.get("shortName") if sender else _normalize_node_id(from_id),
        "sender_longName": sender.get("longName") if sender else _normalize_node_id(from_id),
        "sender_displayName": sender.get("displayName") if sender else _node_display(from_id),
        "recipient_shortName": recipient.get("shortName") if recipient else (_normalize_node_id(to_id) if to_id else "^all"),
        "recipient_longName": recipient.get("longName") if recipient else (_normalize_node_id(to_id) if to_id else "broadcast"),
        "recipient_displayName": recipient.get("displayName") if recipient else (_node_display(to_id) if to_id else "broadcast>broadcast"),
        "sender_name": sender.get("longName") if sender else _normalize_node_id(from_id),
        "recipient_name": recipient.get("longName") if recipient else (_normalize_node_id(to_id) if to_id else "broadcast"),
        "channel": channel_index if channel_index is not None else channel_name,
        "channel_name": channel_label,
        "text": text,
        "kind": "dm" if is_dm else "channel",
    }
    _append_message(msg_item)


# --------------------------- connection loop ---------------------------


def _connect_tcp() -> Any:
    return meshtastic.tcp_interface.TCPInterface(hostname=MESHTASTIC_HOST, portNumber=MESHTASTIC_TCP_PORT)


def _connect_serial() -> Any:
    return meshtastic.serial_interface.SerialInterface(devPath=MESHTASTIC_SERIAL_PORT)


def _interface_ok(interface: Any) -> bool:
    try:
        si = getattr(interface, "serialInterface", None)
        if si is not None and hasattr(si, "is_open"):
            return bool(si.is_open)
    except Exception:
        pass
    try:
        sock = getattr(interface, "socket", None)
        if sock is not None and hasattr(sock, "fileno"):
            return sock.fileno() != -1
    except Exception:
        pass
    return True


def _tcp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _subscribe_events() -> None:
    global _subscribed
    if _subscribed:
        return
    pub.subscribe(on_receive, "meshtastic.receive")
    _subscribed = True


def _connect_loop() -> None:
    global _interface, _last_error, _connected_via

    _subscribe_events()
    next_snapshot_at = 0.0

    while not _stop_event.is_set():
        if _suspend_connect.is_set():
            # Exclusive command is running; keep the port free.
            try:
                if _interface is not None:
                    _interface.close()
            except Exception:
                pass
            _interface = None
            _connected_via = None
            next_snapshot_at = 0.0
            time.sleep(0.2)
            continue

        if _interface is not None and _interface_ok(_interface):
            now = time.time()
            if now >= next_snapshot_at:
                _snapshot_nodes(_interface)
                next_snapshot_at = now + max(2.0, NODE_SNAPSHOT_INTERVAL_SECONDS)
            time.sleep(1)
            continue

        _interface = None
        _connected_via = None
        _last_error = None
        next_snapshot_at = 0.0

        if MESHTASTIC_HOST:
            if _tcp_reachable(MESHTASTIC_HOST, MESHTASTIC_TCP_PORT):
                try:
                    _log(f"Connecting via TCP {MESHTASTIC_HOST}:{MESHTASTIC_TCP_PORT}")
                    _interface = _connect_tcp()
                    _connected_via = f"tcp:{MESHTASTIC_HOST}:{MESHTASTIC_TCP_PORT}"
                    _log(f"Connected via {_connected_via}")
                except Exception as exc:
                    _last_error = f"tcp failed: {exc!r}"
                    _log(_last_error)
                    _interface = None
            else:
                _last_error = f"tcp unreachable: {MESHTASTIC_HOST}:{MESHTASTIC_TCP_PORT}"
                _log(_last_error)

        if _interface is None:
            try:
                _log(f"Connecting via serial {MESHTASTIC_SERIAL_PORT}")
                _interface = _connect_serial()
                _connected_via = f"serial:{MESHTASTIC_SERIAL_PORT}"
                _log(f"Connected via {_connected_via}")
            except Exception as exc:
                _last_error = f"serial failed: {exc!r}"
                _log(_last_error)
                _interface = None

        time.sleep(5)


# --------------------------- CLI bridge ---------------------------


def _cli_connection_args() -> List[str]:
    if MESHTASTIC_HOST and _tcp_reachable(MESHTASTIC_HOST, MESHTASTIC_TCP_PORT):
        return ["--host", MESHTASTIC_HOST]
    return ["--port", MESHTASTIC_SERIAL_PORT]


def _run_cli(extra_args: List[str], timeout: int = CLI_TIMEOUT) -> Dict[str, Any]:
    args = list(extra_args)
    if "--timeout" not in args:
        args += ["--timeout", str(timeout)]
    if "--wait-to-disconnect" not in args:
        args += ["--wait-to-disconnect", "1"]

    cmd = [sys.executable, "-m", "meshtastic"] + _cli_connection_args() + args

    # If we're on serial, the listener interface holds the port open.
    # Suspend the connect loop to free the device for the CLI.
    _suspend_connect.set()
    try:
        try:
            if _interface is not None:
                _interface.close()
        except Exception:
            pass
        # Give the OS a moment to release the lock.
        time.sleep(0.25)
    except Exception:
        pass

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=max(timeout + 10, 20))
    except Exception as exc:
        _suspend_connect.clear()
        return {
            "ok": False,
            "data": {
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
                "cmd": " ".join(shlex.quote(c) for c in cmd),
            },
            "errors": [f"cli_exec_failed: {exc}"],
        }

    payload = {
        "returncode": int(res.returncode),
        "stdout": _redact_text_secrets((res.stdout or "").strip()),
        "stderr": _redact_text_secrets((res.stderr or "").strip()),
        "cmd": " ".join(shlex.quote(c) for c in cmd),
    }

    if res.returncode != 0:
        _suspend_connect.clear()
        return {"ok": False, "data": payload, "errors": [payload.get("stderr") or "cli_failed"]}
    _suspend_connect.clear()
    return {"ok": True, "data": payload, "errors": []}


def _payload_channel_index(payload: Dict[str, Any]) -> Optional[int]:
    idx = payload.get("ch_index", payload.get("channelIndex", payload.get("channel_index")))
    return _coerce_int(idx)


def _payload_dest(payload: Dict[str, Any]) -> Optional[str]:
    dest = payload.get("dest", payload.get("destination"))
    if dest is None:
        return None
    s = str(dest).strip()
    return s or None


def _args_with_dest(base: List[str], payload: Dict[str, Any]) -> List[str]:
    args = list(base)
    dest = _payload_dest(payload)
    if dest:
        args += ["--dest", dest]
    return args


def _args_with_channel(base: List[str], payload: Dict[str, Any]) -> List[str]:
    args = list(base)
    idx = _payload_channel_index(payload)
    if idx is not None:
        args += ["--ch-index", str(idx)]
    return args


def _execute_sendtext(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text", payload.get("message"))
    if not text:
        return _wrap_err("missing text")

    dest = _payload_dest(payload)
    ch_idx = _payload_channel_index(payload)
    private = bool(payload.get("private", False))
    ack = bool(payload.get("ack", False))

    used_cli = private or (_interface is None)
    channel_label = "Primary"

    if not used_cli:
        try:
            resolved_idx, channel_label = _resolve_send_channel(_interface, None, ch_idx)
            kwargs: Dict[str, Any] = {}
            if dest:
                kwargs["destinationId"] = dest
            if isinstance(resolved_idx, int):
                kwargs["channelIndex"] = resolved_idx
            _interface.sendText(str(text), **kwargs)
        except Exception:
            used_cli = True

    cli_result: Dict[str, Any] = {"ok": True, "data": {"stdout": "", "stderr": "", "returncode": 0, "cmd": "interface.sendText"}, "errors": []}
    if used_cli:
        args = ["--sendtext", str(text)]
        if private:
            args.append("--private")
        if ack:
            args.append("--ack")
        args = _args_with_dest(args, payload)
        args = _args_with_channel(args, payload)
        cli_result = _run_cli(args)
        if not cli_result.get("ok"):
            return cli_result

    sender = _find_node("local") or _upsert_node("local", short_name="local", long_name="local")
    recipient = _find_node(dest) if dest else None
    _append_message(
        {
            "time": _now_ts(),
            "rx_time": time.time(),
            "from_id": "local",
            "to_id": _normalize_node_id(dest) if dest else "^all",
            "sender_shortName": sender.get("shortName"),
            "sender_longName": sender.get("longName"),
            "sender_displayName": sender.get("displayName"),
            "recipient_shortName": recipient.get("shortName") if recipient else (dest or "broadcast"),
            "recipient_longName": recipient.get("longName") if recipient else (dest or "broadcast"),
            "recipient_displayName": recipient.get("displayName") if recipient else _display_name(dest or "broadcast", dest or "broadcast", dest or "broadcast"),
            "sender_name": "local",
            "recipient_name": recipient.get("longName") if recipient else (dest or "broadcast"),
            "channel": ch_idx if ch_idx is not None else "Primary",
            "channel_name": channel_label,
            "text": str(text),
            "kind": "dm" if dest else "channel",
            "direction": "outbound",
        }
    )

    return _wrap_ok(
        {
            "sent": True,
            "destination": dest or "broadcast",
            "channel": channel_label,
            "transport": "cli" if used_cli else "interface",
            "cli": cli_result.get("data"),
        }
    )


def _execute_cli_command(command_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    args: List[str] = []

    if command_name == "info":
        args = ["--info"]
    elif command_name == "nodes":
        args = ["--nodes"]
        show_fields = payload.get("show_fields")
        if show_fields:
            args += ["--show-fields", str(show_fields)]
    elif command_name == "request_telemetry":
        telem_type = payload.get("type")
        args = ["--request-telemetry"] + ([str(telem_type)] if telem_type else [])
        args = _args_with_dest(args, payload)
    elif command_name == "request_position":
        args = _args_with_dest(["--request-position"], payload)
    elif command_name == "traceroute":
        dest = _payload_dest(payload)
        if not dest:
            return _wrap_err("missing dest")
        args = ["--traceroute", dest]
    elif command_name == "get":
        field = payload.get("field")
        if not field:
            return _wrap_err("missing field")
        args = ["--get", str(field)]
    elif command_name == "set":
        field = payload.get("field")
        value = payload.get("value")
        if field is None or value is None:
            return _wrap_err("missing field or value")
        args = ["--set", str(field), str(value)]
    elif command_name == "configure":
        path = payload.get("path", payload.get("file"))
        if not path:
            return _wrap_err("missing path")
        args = ["--configure", str(path)]
    elif command_name == "export_config":
        path = payload.get("path", payload.get("file"))
        # By default, avoid returning sensitive config material (channel_url, pins, etc) in stdout.
        # If no file is provided, export to a file under /data/exports and return the CLI result.
        if not path and not MESHTASTIC_SENSITIVE_OUTPUT_ENABLED:
            try:
                export_dir = DATA_DIR / "exports"
                export_dir.mkdir(parents=True, exist_ok=True)
                path = str(export_dir / f"meshtastic_export_{int(time.time())}.yml")
            except Exception:
                path = "/data/exports/meshtastic_export.yml"
        args = ["--export-config"] + ([str(path)] if path else [])
    elif command_name == "ch_set":
        field = payload.get("field")
        value = payload.get("value")
        if field is None or value is None:
            return _wrap_err("missing field or value")
        args = ["--ch-set", str(field), str(value)]
        args = _args_with_channel(args, payload)
    elif command_name == "ch_add":
        name = payload.get("name", payload.get("channel"))
        if not name:
            return _wrap_err("missing channel name")
        args = ["--ch-add", str(name)]
    elif command_name == "ch_del":
        args = _args_with_channel(["--ch-del"], payload)
    elif command_name == "ch_enable":
        args = _args_with_channel(["--ch-enable"], payload)
    elif command_name == "ch_disable":
        args = _args_with_channel(["--ch-disable"], payload)
    elif command_name == "set_owner":
        value = payload.get("value", payload.get("owner"))
        if value is None:
            return _wrap_err("missing value")
        args = ["--set-owner", str(value)]
    elif command_name == "set_owner_short":
        value = payload.get("value", payload.get("owner_short"))
        if value is None:
            return _wrap_err("missing value")
        args = ["--set-owner-short", str(value)]
    elif command_name == "set_ham":
        value = payload.get("value")
        if value is None:
            return _wrap_err("missing value")
        args = ["--set-ham", str(value)]
    elif command_name == "set_is_unmessageable":
        value = payload.get("value")
        if value is None:
            return _wrap_err("missing value")
        args = ["--set-is-unmessageable", str(value)]
    elif command_name == "setlat":
        value = payload.get("value")
        if value is None:
            return _wrap_err("missing value")
        args = ["--setlat", str(value)]
    elif command_name == "setlon":
        value = payload.get("value")
        if value is None:
            return _wrap_err("missing value")
        args = ["--setlon", str(value)]
    elif command_name == "setalt":
        value = payload.get("value")
        if value is None:
            return _wrap_err("missing value")
        args = ["--setalt", str(value)]
    elif command_name == "remove_position":
        args = ["--remove-position"]
    elif command_name == "pos_fields":
        fields = payload.get("fields") or payload.get("values") or []
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(",") if f.strip()]
        args = ["--pos-fields"] + [str(x) for x in fields]
    elif command_name == "qr":
        if not MESHTASTIC_SENSITIVE_OUTPUT_ENABLED:
            return _wrap_err("sensitive_output_disabled: set MESHTASTIC_SENSITIVE_OUTPUT_ENABLED=true to allow QR/URL output")
        args = _args_with_channel(["--qr"], payload)
    elif command_name == "qr_all":
        if not MESHTASTIC_SENSITIVE_OUTPUT_ENABLED:
            return _wrap_err("sensitive_output_disabled: set MESHTASTIC_SENSITIVE_OUTPUT_ENABLED=true to allow QR/URL output")
        args = ["--qr-all"]
    elif command_name == "reply":
        args = ["--reply"]
    elif command_name == "request_time":
        args = ["--set-time"]
    elif command_name == "reboot":
        args = _args_with_dest(["--reboot"], payload)
    elif command_name == "shutdown":
        args = _args_with_dest(["--shutdown"], payload)
    elif command_name == "factory_reset":
        args = _args_with_dest(["--factory-reset"], payload)
    elif command_name == "factory_reset_device":
        args = _args_with_dest(["--factory-reset-device"], payload)
    elif command_name == "reset_nodedb":
        args = _args_with_dest(["--reset-nodedb"], payload)
    elif command_name == "remove_node":
        target = payload.get("target") or payload.get("node")
        if not target:
            return _wrap_err("missing target")
        args = _args_with_dest(["--remove-node", str(target)], payload)
    elif command_name == "set_favorite_node":
        target = payload.get("target") or payload.get("node")
        if not target:
            return _wrap_err("missing target")
        args = _args_with_dest(["--set-favorite-node", str(target)], payload)
    elif command_name == "remove_favorite_node":
        target = payload.get("target") or payload.get("node")
        if not target:
            return _wrap_err("missing target")
        args = _args_with_dest(["--remove-favorite-node", str(target)], payload)
    elif command_name == "set_ignored_node":
        target = payload.get("target") or payload.get("node")
        if not target:
            return _wrap_err("missing target")
        args = _args_with_dest(["--set-ignored-node", str(target)], payload)
    elif command_name == "remove_ignored_node":
        target = payload.get("target") or payload.get("node")
        if not target:
            return _wrap_err("missing target")
        args = _args_with_dest(["--remove-ignored-node", str(target)], payload)
    elif command_name == "device_metadata":
        args = _args_with_dest(["--device-metadata"], payload)
    else:
        return _wrap_err(f"unsupported command: {command_name}")

    ack = bool(payload.get("ack", False))
    if ack:
        args.append("--ack")

    timeout = _coerce_int(payload.get("timeout")) or CLI_TIMEOUT
    return _run_cli(args, timeout=timeout)


def _build_local_info() -> Dict[str, Any]:
    local: Dict[str, Any] = {}
    if _interface is not None:
        try:
            node = getattr(_interface, "localNode", None)
            my = None
            try:
                my = getattr(node, "getMyNodeInfo", None)
                my = my() if callable(my) else None
            except Exception:
                my = None
            local = {
                "nodeNum": getattr(node, "nodeNum", None),
                "myNode": my or {},
                "channels": _list_channels(_interface),
            }
        except Exception:
            local = {}
    return {
        "connected": _interface is not None,
        "connected_via": _connected_via,
        "last_error": _last_error,
        "local": local,
    }


def _execute_info_quick(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "data": _build_local_info(), "errors": []}


def _execute_nodes_quick(payload: Dict[str, Any]) -> Dict[str, Any]:
    limit = _coerce_int(payload.get("limit")) or 500
    if _interface is not None:
        _snapshot_nodes(_interface)
    with _lock:
        items = sorted(_nodes.values(), key=lambda r: (r.get("shortName") or "", r.get("id") or ""))[: max(1, min(2000, limit))]
    return {
        "ok": True,
        "data": {"nodes": items, "count": len(items), "format": "shortName>longName"},
        "errors": [],
    }


@dataclass
class CommandSpec:
    name: str
    safety: str  # safe | guarded | blocked
    implemented: bool
    description: str
    args: List[str]
    feature: Optional[str] = None
    handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None


_COMMANDS: Dict[str, CommandSpec] = {}


def _register_command(spec: CommandSpec) -> None:
    _COMMANDS[spec.name] = spec


def _build_command_registry() -> None:
    implemented_cli = {
        "info",
        "nodes",
        "sendtext",
        "request_telemetry",
        "request_position",
        "traceroute",
        "get",
        "set",
        "configure",
        "export_config",
        "ch_set",
        "ch_add",
        "ch_del",
        "ch_enable",
        "ch_disable",
        "set_owner",
        "set_owner_short",
        "set_ham",
        "set_is_unmessageable",
        "setlat",
        "setlon",
        "setalt",
        "remove_position",
        "pos_fields",
        "qr",
        "qr_all",
        "reply",
        "reboot",
        "shutdown",
        "factory_reset",
        "factory_reset_device",
        "reset_nodedb",
        "remove_node",
        "set_favorite_node",
        "remove_favorite_node",
        "set_ignored_node",
        "remove_ignored_node",
        "device_metadata",
    }

    guarded = {
        "reboot",
        "shutdown",
        "factory_reset",
        "factory_reset_device",
        "reset_nodedb",
        "remove_node",
        "set_favorite_node",
        "remove_favorite_node",
        "set_ignored_node",
        "remove_ignored_node",
    }

    descriptions: Dict[str, str] = {
        "info": "Read and display local radio configuration",
        "nodes": "List known nodes",
        "sendtext": "Send text message",
        "request_telemetry": "Request telemetry from destination node",
        "request_position": "Request position from destination node",
        "traceroute": "Run traceroute across mesh",
        "get": "Get config field",
        "set": "Set config field",
        "configure": "Apply configuration file",
        "export_config": "Export configuration",
        "ch_set": "Set channel field",
        "ch_add": "Add channel",
        "ch_del": "Delete channel",
        "ch_enable": "Enable channel",
        "ch_disable": "Disable channel",
        "set_owner": "Set owner long name",
        "set_owner_short": "Set owner short name",
        "set_ham": "Set licensed ham ID",
        "set_is_unmessageable": "Set messageability flag",
        "setlat": "Set fixed latitude",
        "setlon": "Set fixed longitude",
        "setalt": "Set fixed altitude",
        "remove_position": "Clear fixed position",
        "pos_fields": "Set position field set",
        "qr": "Show QR for channel",
        "qr_all": "Show QR for all channels",
        "reply": "Reply to latest message",
        "reboot": "Reboot destination node",
        "shutdown": "Shutdown destination node",
        "factory_reset": "Reset config preserving keys",
        "factory_reset_device": "Reset device including keys",
        "reset_nodedb": "Clear NodeDB",
        "remove_node": "Remove specific node from NodeDB",
        "set_favorite_node": "Favorite node",
        "remove_favorite_node": "Unfavorite node",
        "set_ignored_node": "Ignore node",
        "remove_ignored_node": "Unignore node",
        "device_metadata": "Fetch device metadata",
        "ble_scan": "Scan BLE devices",
        "power_riden": "Power testing using Riden PSU",
        "power_ppk2_meter": "Power profiling using PPK2 meter",
        "power_ppk2_supply": "Power profiling using PPK2 supply mode",
        "power_sim": "Power simulation mode",
        "gpio_wrb": "Remote GPIO write",
        "gpio_rd": "Remote GPIO read",
        "gpio_watch": "Remote GPIO watch",
        "tunnel": "Enable tunnel mode",
    }

    arg_map: Dict[str, List[str]] = {
        "sendtext": ["text", "dest?", "ch_index?", "private?", "ack?"],
        "request_telemetry": ["dest", "type?"],
        "request_position": ["dest"],
        "traceroute": ["dest"],
        "get": ["field"],
        "set": ["field", "value"],
        "configure": ["path"],
        "export_config": ["path?"],
        "ch_set": ["field", "value", "ch_index?"],
        "ch_add": ["name"],
        "ch_del": ["ch_index"],
        "ch_enable": ["ch_index"],
        "ch_disable": ["ch_index"],
        "set_owner": ["value"],
        "set_owner_short": ["value"],
        "set_ham": ["value"],
        "set_is_unmessageable": ["value"],
        "setlat": ["value"],
        "setlon": ["value"],
        "setalt": ["value"],
        "pos_fields": ["fields[]"],
        "reboot": ["dest?"],
        "shutdown": ["dest?"],
        "factory_reset": ["dest?"],
        "factory_reset_device": ["dest?"],
        "reset_nodedb": ["dest?"],
        "remove_node": ["target", "dest?"],
        "set_favorite_node": ["target", "dest?"],
        "remove_favorite_node": ["target", "dest?"],
        "set_ignored_node": ["target", "dest?"],
        "remove_ignored_node": ["target", "dest?"],
    }

    for cmd in sorted(implemented_cli):
        safety = "guarded" if cmd in guarded else "safe"
        if cmd == "sendtext":
            handler = _execute_sendtext
        elif cmd == "info":
            handler = _execute_info_quick
        elif cmd == "nodes":
            handler = _execute_nodes_quick
        else:
            handler = (lambda payload, c=cmd: _execute_cli_command(c, payload))
        _register_command(
            CommandSpec(
                name=cmd,
                safety=safety,
                implemented=True,
                description=descriptions.get(cmd, cmd),
                args=arg_map.get(cmd, []),
                handler=handler,
            )
        )

    # Explicit stubs for hardware-specialized groups.
    for cmd, feature in [
        ("ble_scan", "ble"),
        ("power_riden", "power"),
        ("power_ppk2_meter", "power"),
        ("power_ppk2_supply", "power"),
        ("power_sim", "power"),
        ("gpio_wrb", "gpio"),
        ("gpio_rd", "gpio"),
        ("gpio_watch", "gpio"),
        ("tunnel", "tunnel"),
    ]:
        _register_command(
            CommandSpec(
                name=cmd,
                safety="blocked",
                implemented=False,
                description=descriptions.get(cmd, cmd),
                args=arg_map.get(cmd, []),
                feature=feature,
                handler=None,
            )
        )


_build_command_registry()


# --------------------------- Command execution ---------------------------


def _command_error_for_spec(spec: CommandSpec) -> Optional[Dict[str, Any]]:
    if spec.safety == "guarded" and not MESHTASTIC_ADMIN_ENABLED:
        return _wrap_err("admin_disabled: set MESHTASTIC_ADMIN_ENABLED=true to enable this command")
    if not spec.implemented:
        feature = spec.feature or "feature"
        return _wrap_err(f"not_enabled:{feature}")
    if spec.handler is None:
        return _wrap_err("handler_missing")
    return None


def _execute_command(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    spec = _COMMANDS.get(name)
    if not spec:
        return _wrap_err(f"unknown command: {name}")

    payload = _normalize_command_payload(payload or {})
    blocked = _command_error_for_spec(spec)
    if blocked is not None:
        return blocked

    result = spec.handler(payload) if spec.handler else _wrap_err("handler_missing")
    if name in ("info", "nodes", "sendtext") and _interface is not None:
        _snapshot_nodes(_interface)
    return result


# --------------------------- startup/shutdown ---------------------------


@app.on_event("startup")
def _startup() -> None:
    global _messages, _telemetry, _nodes, _mqtt_cfg, _mqtt_messages

    _messages = _load_json(MSG_FILE, [])
    _telemetry = _load_json(TEL_FILE, [])

    nodes_raw = _load_json(NODE_FILE, [])
    _nodes = {}
    if isinstance(nodes_raw, list):
        for rec in nodes_raw:
            if not isinstance(rec, dict):
                continue
            nid = _normalize_node_id(rec.get("id"))
            if not nid:
                continue
            short_name = rec.get("shortName") or nid
            long_name = rec.get("longName") or short_name
            _nodes[nid] = {
                "id": nid,
                "nodeNum": rec.get("nodeNum"),
                "shortName": short_name,
                "longName": long_name,
                "displayName": _display_name(short_name, long_name, nid),
                "first_heard": rec.get("first_heard") or _now_ts(),
                "last_heard": rec.get("last_heard") or _now_ts(),
            }

    _mqtt_cfg = _default_mqtt_cfg()
    persisted_cfg = _load_json(MQTT_CFG_FILE, {})
    if isinstance(persisted_cfg, dict):
        _mqtt_cfg.update(persisted_cfg)

    _mqtt_messages = _load_json(MQTT_MSG_FILE, [])
    if not isinstance(_mqtt_messages, list):
        _mqtt_messages = []
    _trim_list(_mqtt_messages)

    t = threading.Thread(target=_connect_loop, daemon=True)
    t.start()

    if bool(_mqtt_cfg.get("enabled")):
        _mqtt_connect_internal()


@app.on_event("shutdown")
def _shutdown() -> None:
    _stop_event.set()
    _mqtt_disconnect_internal()
    try:
        if _interface is not None:
            _interface.close()
    except Exception:
        pass


# --------------------------- base endpoints ---------------------------


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "meshtastic",
        "connected": _interface is not None,
        "connected_via": _connected_via,
        "last_error": _last_error,
        "admin_enabled": MESHTASTIC_ADMIN_ENABLED,
        "mqtt": _mqtt_status_data(),
    }


@app.get("/messages")
def messages(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    with _lock:
        items = list(_messages)[-limit:]
    return _wrap_ok({"items": items, "count": len(items), "total": len(_messages)})


@app.get("/telemetry")
def telemetry(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    with _lock:
        lines = list(_telemetry)[-limit:]
    return _wrap_ok({"lines": lines, "count": len(lines), "total": len(_telemetry)})


@app.post("/send")
def send(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    # Backwards-compatible alias.
    return _execute_command("sendtext", payload)


# --------------------------- command namespace ---------------------------


@app.get("/commands")
def commands() -> Dict[str, Any]:
    items = []
    for spec in sorted(_COMMANDS.values(), key=lambda s: s.name):
        items.append(
            {
                "name": spec.name,
                "safety": spec.safety,
                "implemented": spec.implemented,
                "description": spec.description,
                "args": spec.args,
                "feature": spec.feature,
            }
        )
    return _wrap_ok({"commands": items, "admin_enabled": MESHTASTIC_ADMIN_ENABLED})


@app.post("/commands/{command_name}")
def command_execute(command_name: str, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command(command_name, payload or {})


# --------------------------- typed aliases ---------------------------


@app.get("/info")
def info() -> Dict[str, Any]:
    # Do not shell out to the CLI here; the CLI needs exclusive access to the serial
    # port and will block/hang while the listener is connected. We instead return
    # the key local runtime values from the already-open interface.
    return _wrap_ok(_build_local_info())


@app.get("/nodes")
def nodes(
    limit: int = Query(default=500, ge=1, le=2000),
    refresh: bool = Query(default=False),
) -> Dict[str, Any]:
    # Normal reads return cached state; opt-in refresh only when explicitly requested.
    if refresh and _interface is not None:
        _snapshot_nodes(_interface)
    with _lock:
        items = sorted(_nodes.values(), key=lambda r: (r.get("shortName") or "", r.get("id") or ""))[:limit]
    return _wrap_ok({"nodes": items, "count": len(items), "format": "shortName>longName"})


@app.get("/channels")
def channels() -> Dict[str, Any]:
    chans = _list_channels(_interface) if _interface is not None else [{"index": 0, "name": "Primary", "role": "PRIMARY"}]
    return _wrap_ok({"channels": chans, "count": len(chans)})


@app.post("/sendtext")
def sendtext(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("sendtext", payload or {})


@app.post("/request-telemetry")
def request_telemetry(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("request_telemetry", payload or {})


@app.post("/request-position")
def request_position(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("request_position", payload or {})


@app.post("/traceroute")
def traceroute(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("traceroute", payload or {})


@app.get("/config/field")
def config_field_get(field: str = Query(...)) -> Dict[str, Any]:
    return _execute_command("get", {"field": field})


@app.post("/config/field")
def config_field_set(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("set", payload or {})


@app.post("/channel/set")
def channel_set(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("ch_set", payload or {})


@app.post("/channel/add")
def channel_add(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("ch_add", payload or {})


@app.post("/channel/delete")
def channel_delete(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    return _execute_command("ch_del", payload or {})


# --------------------------- MQTT endpoints ---------------------------


@app.get("/mqtt/status")
def mqtt_status() -> Dict[str, Any]:
    return _wrap_ok(_mqtt_status_data())


@app.get("/mqtt/config")
def mqtt_config_get() -> Dict[str, Any]:
    return _wrap_ok({"config": _mqtt_redacted_cfg()})


@app.post("/mqtt/config")
def mqtt_config_set(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    allowed = {
        "enabled",
        "host",
        "port",
        "username",
        "password",
        "tls",
        "client_id",
        "keepalive",
        "qos",
        "topics",
        "downlink_topic",
    }

    restart = bool(payload.get("restart", False))
    with _mqtt_lock:
        for key, value in (payload or {}).items():
            if key in allowed:
                _mqtt_cfg[key] = value
        _save_mqtt_cfg()

    if bool(_mqtt_cfg.get("enabled")):
        if restart:
            return _mqtt_connect_internal()
    else:
        _mqtt_disconnect_internal()

    return _wrap_ok({"config": _mqtt_redacted_cfg(), "restart_required": not restart})


@app.get("/mqtt/topics")
def mqtt_topics() -> Dict[str, Any]:
    with _mqtt_lock:
        seen = sorted({m.get("topic") for m in _mqtt_messages if m.get("topic")})
        configured = [str(t) for t in (_mqtt_cfg.get("topics") or []) if str(t).strip()]
        subscribed = sorted(_mqtt_subscriptions)
    return _wrap_ok({"configured": configured, "subscribed": subscribed, "seen": seen})


@app.post("/mqtt/connect")
def mqtt_connect() -> Dict[str, Any]:
    with _mqtt_lock:
        _mqtt_cfg["enabled"] = True
        _save_mqtt_cfg()
    return _mqtt_connect_internal()


@app.post("/mqtt/disconnect")
def mqtt_disconnect() -> Dict[str, Any]:
    with _mqtt_lock:
        _mqtt_cfg["enabled"] = False
        _save_mqtt_cfg()
    return _mqtt_disconnect_internal()


@app.post("/mqtt/publish-json")
def mqtt_publish_json(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    topic = _sanitize_topic(str(payload.get("topic") or ""))
    if not topic:
        return _wrap_err("missing topic")
    qos = _coerce_int(payload.get("qos"))
    if qos is None:
        qos = int(_mqtt_cfg.get("qos") or 0)
    retain = bool(payload.get("retain", False))
    body = payload.get("payload")
    raw = json.dumps(body if body is not None else {}, separators=(",", ":")).encode("utf-8")
    return _mqtt_publish(topic, raw, qos=qos, retain=retain)


@app.post("/mqtt/publish-protobuf")
def mqtt_publish_protobuf(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    topic = _sanitize_topic(str(payload.get("topic") or ""))
    if not topic:
        return _wrap_err("missing topic")

    qos = _coerce_int(payload.get("qos"))
    if qos is None:
        qos = int(_mqtt_cfg.get("qos") or 0)
    retain = bool(payload.get("retain", False))

    payload_b64 = payload.get("payload_b64")
    payload_hex = payload.get("payload_hex")
    if payload_b64:
        try:
            data = base64.b64decode(str(payload_b64))
        except Exception as exc:
            return _wrap_err(f"invalid payload_b64: {exc}")
    elif payload_hex:
        try:
            data = bytes.fromhex(str(payload_hex))
        except Exception as exc:
            return _wrap_err(f"invalid payload_hex: {exc}")
    else:
        return _wrap_err("missing payload_b64 or payload_hex")

    return _mqtt_publish(topic, data, qos=qos, retain=retain)


@app.get("/mqtt/messages")
def mqtt_messages(limit: int = Query(default=100, ge=1, le=500)) -> Dict[str, Any]:
    with _mqtt_lock:
        items = list(_mqtt_messages)[-limit:]
    return _wrap_ok({"items": items, "count": len(items), "total": len(_mqtt_messages)})


@app.post("/mqtt/subscribe")
def mqtt_subscribe(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    topic = _sanitize_topic(str(payload.get("topic") or ""))
    if not topic:
        return _wrap_err("missing topic")

    qos = _coerce_int(payload.get("qos"))
    if qos is None:
        qos = int(_mqtt_cfg.get("qos") or 0)

    with _mqtt_lock:
        topics = list(_mqtt_cfg.get("topics") or [])
        if topic not in topics:
            topics.append(topic)
        _mqtt_cfg["topics"] = topics
        _save_mqtt_cfg()
        client = _mqtt_client
        connected = _mqtt_connected

    if client is not None and connected:
        try:
            client.subscribe(topic, qos=qos)
            with _mqtt_lock:
                _mqtt_subscriptions.add(topic)
        except Exception as exc:
            return _wrap_err(f"subscribe failed: {exc}")

    return _wrap_ok({"subscribed": topic, "qos": qos})


@app.post("/mqtt/unsubscribe")
def mqtt_unsubscribe(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    topic = _sanitize_topic(str(payload.get("topic") or ""))
    if not topic:
        return _wrap_err("missing topic")

    with _mqtt_lock:
        topics = [t for t in (_mqtt_cfg.get("topics") or []) if str(t) != topic]
        _mqtt_cfg["topics"] = topics
        _save_mqtt_cfg()
        client = _mqtt_client
        connected = _mqtt_connected

    if client is not None and connected:
        try:
            client.unsubscribe(topic)
        except Exception:
            pass
    with _mqtt_lock:
        _mqtt_subscriptions.discard(topic)

    return _wrap_ok({"unsubscribed": topic})


@app.post("/mqtt/downlink/sendtext")
def mqtt_downlink_sendtext(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    text = payload.get("text") or payload.get("message")
    if not text:
        return _wrap_err("missing text")

    topic = _sanitize_topic(str(payload.get("topic") or _mqtt_cfg.get("downlink_topic") or MQTT_DEFAULT_DOWNLINK_TOPIC))
    qos = _coerce_int(payload.get("qos"))
    if qos is None:
        qos = int(_mqtt_cfg.get("qos") or 0)

    body = {
        "type": "sendtext",
        "text": str(text),
        "dest": str(payload.get("dest") or "^all"),
        "channel": _payload_channel_index(payload),
        "ts": _now_ts(),
    }
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    published = _mqtt_publish(topic, raw, qos=qos, retain=False)
    if not published.get("ok"):
        return published
    return _wrap_ok({"sent": True, "topic": topic, "payload": body})


@app.exception_handler(Exception)
async def unhandled_exception(_, exc: Exception):
    return JSONResponse(status_code=500, content=_wrap_err(str(exc)))
