#!/usr/bin/env python3
import json
import os
import queue
import re
import signal
import subprocess
import threading
import time
import uuid
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt
import redis

BROKER_HOST = os.getenv("BROKER_HOST", "100.90.138.26")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
BROKER_USER = os.getenv("BROKER_USER") or None
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD") or None
MQTT_CLIENT_ID = (os.getenv("MQTT_CLIENT_ID", "real-joe") or "real-joe").strip()

QUERY_TOPIC = os.getenv("QUERY_TOPIC", "susnet/agent/query")
REPLY_TOPIC = os.getenv("REPLY_TOPIC", "susnet/agent/reply")
ACK_TOPIC = os.getenv("ACK_TOPIC", "susnet/agent/ack")
PROGRESS_TOPIC = os.getenv("PROGRESS_TOPIC", "susnet/agent/progress")
CONTROL_TOPIC = os.getenv("CONTROL_TOPIC", "susnet/agent/control")
ERROR_TOPIC = os.getenv("ERROR_TOPIC", "susnet/agent/error")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "susnet/agent/dlq")
HEALTH_TOPIC = os.getenv("HEALTH_TOPIC", "susnet/agent/events/health")
POLICY_EVENT_TOPIC = os.getenv("POLICY_EVENT_TOPIC", "susnet/agent/events/policy")

REDIS_URL = os.getenv("REDIS_URL", "redis://real-joe-redis:6379/0")
REDIS_PREFIX = (os.getenv("REDIS_PREFIX", "real-joe") or "real-joe").strip()
REDIS_TTL_SECONDS = int(os.getenv("REDIS_TTL_SECONDS", "86400"))

STATE_PATH = Path(os.getenv("STATE_PATH", "/data/Joes-Office/real-joe/state.json"))
SNAPSHOT_SECONDS = int(os.getenv("SNAPSHOT_SECONDS", "20"))
STILL_WORKING_INTERVAL_SECONDS = int(os.getenv("STILL_WORKING_INTERVAL_SECONDS", "12"))

ROLL_OUT_MODE = (os.getenv("ROLLOUT_MODE", "dedicated") or "dedicated").strip().lower()
CANARY_PERCENT = max(0, min(100, int(os.getenv("CANARY_PERCENT", "10"))))
PILOT_CHANNEL_FINGERPRINTS = {
    x.strip().lower()
    for x in (os.getenv("PILOT_CHANNEL_FINGERPRINTS", "") or "").split(",")
    if x.strip()
}

RF_MAX_CHUNKS = int(os.getenv("RF_MAX_CHUNKS", "5"))
RF_CHUNK_CHARS = int(os.getenv("RF_CHUNK_CHARS", "110"))
RF_RESPONSE_HEADROOM_CHARS = int(os.getenv("RF_RESPONSE_HEADROOM_CHARS", "30"))
MIN_INTER_CHUNK_DELAY_SECONDS = float(os.getenv("MIN_INTER_CHUNK_DELAY_SECONDS", "1.0"))
INITIAL_RESPONSE_DELAY_SECONDS = float(os.getenv("INITIAL_RESPONSE_DELAY_SECONDS", "0.0"))

OPENCLAW_ENABLED = os.getenv("OPENCLAW_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
OPENCLAW_GATEWAY_CONTAINER = os.getenv("OPENCLAW_GATEWAY_CONTAINER", "openclaw_openclaw-gateway_1")
OPENCLAW_AGENT_TIMEOUT_SECONDS = int(os.getenv("OPENCLAW_AGENT_TIMEOUT_SECONDS", "30"))
OPENCLAW_WAIT_TIMEOUT_MS = int(os.getenv("OPENCLAW_WAIT_TIMEOUT_MS", "40000"))
OPENCLAW_POLL_COUNT = max(1, int(os.getenv("OPENCLAW_POLL_COUNT", "3")))
OPENCLAW_CALL_TIMEOUT_SECONDS = int(os.getenv("OPENCLAW_CALL_TIMEOUT_SECONDS", "45"))
OPENCLAW_EXTRA_SYSTEM_PROMPT = (
    os.getenv("OPENCLAW_EXTRA_SYSTEM_PROMPT", "")
    or ""
).strip()
OPENCLAW_CIRCUIT_FAIL_THRESHOLD = max(1, int(os.getenv("OPENCLAW_CIRCUIT_FAIL_THRESHOLD", "1")))
OPENCLAW_CIRCUIT_OPEN_SECONDS = max(30, int(os.getenv("OPENCLAW_CIRCUIT_OPEN_SECONDS", "900")))

OLLAMA_DIRECT_ENABLED = os.getenv("OLLAMA_DIRECT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
OLLAMA_CONTAINER = (os.getenv("OLLAMA_CONTAINER", "openclaw-ollama") or "openclaw-ollama").strip()
OLLAMA_MODEL = (os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b") or "qwen2.5:0.5b").strip()
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
OLLAMA_URL = (os.getenv("OLLAMA_URL") or "").strip()
OLLAMA_IP_CACHE_SECONDS = int(os.getenv("OLLAMA_IP_CACHE_SECONDS", "120"))

OPERATOR_TOKEN = (os.getenv("OPERATOR_TOKEN", "") or "").strip()
GLOBAL_PAUSED_DEFAULT = os.getenv("GLOBAL_PAUSED_DEFAULT", "false").strip().lower() in {"1", "true", "yes", "on"}
TOOLS_PAUSED_DEFAULT = os.getenv("TOOLS_PAUSED_DEFAULT", "false").strip().lower() in {"1", "true", "yes", "on"}
ESCALATION_PAUSED_DEFAULT = os.getenv("ESCALATION_PAUSED_DEFAULT", "false").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_SOFT_SHUTDOWN = os.getenv("ENABLE_SOFT_SHUTDOWN", "false").strip().lower() in {"1", "true", "yes", "on"}
SOFT_SHUTDOWN_COMMAND = (os.getenv("SOFT_SHUTDOWN_COMMAND", "") or "").strip()

SUB_TOPICS = [
    (QUERY_TOPIC, 0),
    (CONTROL_TOPIC, 0),
    ("meshbox/agent/events/rx", 0),
    ("meshbox/agent/events/policy", 0),
    ("meshbox/agent/events/health", 0),
    ("meshbox/agent/events/nodes", 0),
]

STOP = threading.Event()
LOCK = threading.Lock()

STATE = {
    "started_ts": int(time.time()),
    "last_rx_ts": None,
    "rx_1h_count": 0,
    "policy_decisions": {},
    "node_count": 0,
    "nodes": {},
    "health": {},
}

RX_EVENTS = deque(maxlen=12000)
POLICY_COUNTER = Counter()
INFLIGHT: Dict[str, Dict[str, Any]] = {}
INFLIGHT_LOCK = threading.Lock()
OPENCLAW_CIRCUIT_LOCK = threading.Lock()
OPENCLAW_CIRCUIT = {
    "fails": 0,
    "open_until": 0,
    "last_error": "",
    "opened_count": 0,
}

REDIS: Optional[redis.Redis] = None
OLLAMA_IP_CACHE = {"ts": 0, "url": None}

HQ_ROOT = Path(os.getenv("HQ_ROOT", "/data/Resevoir-Comms-HQ"))
HQ_LIBRARY_ROOT = Path(os.getenv("HQ_LIBRARY_ROOT", str(HQ_ROOT / "Library")))
HQ_OFFICES_ROOT = Path(os.getenv("HQ_OFFICES_ROOT", str(HQ_ROOT / "Offices")))
HQ_DESKS_ROOT = Path(os.getenv("HQ_DESKS_ROOT", str(HQ_ROOT / "Desks")))
EXPERT_AGENT_DEFAULT = (os.getenv("EXPERT_AGENT_DEFAULT", "Mr-Pink") or "Mr-Pink").strip()
EXPERT_ALLOWLIST_NODE_IDS_RAW = tuple(
    x.strip()
    for x in (os.getenv("EXPERT_ALLOWLIST_NODE_IDS", "") or "").split(",")
    if x.strip()
)
EXPERT_BUDGET_BYTES = max(1, int(os.getenv("EXPERT_BUDGET_BYTES", str(500 * 1024 * 1024))))
LIBRARY_CAP_BYTES = max(1, int(os.getenv("LIBRARY_CAP_BYTES", str(20 * 1024 * 1024 * 1024))))
LIBRARY_THRESHOLD_BYTES_RAW = (
    os.getenv("LIBRARY_THRESHOLD_BYTES", "5368709120,10737418240,16106127360")
    or "5368709120,10737418240,16106127360"
)
EXPERT_FLOW_TTL_SECONDS = max(300, int(os.getenv("EXPERT_FLOW_TTL_SECONDS", "86400")))
EXPERT_TRIGGER_RE = re.compile(r"\b(become\s+an?\s+expert|become\s+expert|expert\s+mode)\b", re.IGNORECASE)


def ts_now() -> int:
    return int(time.time())


def _coerce_positive_int(value, default):
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _coerce_positive_float(value, default):
    try:
        n = float(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _chunk_text_words(text: str, chunk_chars: int, max_chunks: int):
    words = _normalize_text(text).split(" ")
    chunks = []
    current = ""
    for word in words:
        if not word:
            continue
        if len(word) > chunk_chars:
            word = word[: max(1, chunk_chars - 1)] + "..."
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= chunk_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            if len(chunks) >= max_chunks:
                break
        current = word
    if current and len(chunks) < max_chunks:
        chunks.append(current)
    return chunks[:max_chunks]


def bounded_chunks(text: str, max_chunks=None, chunk_chars=None, max_output_chars=None):
    max_chunks = _coerce_positive_int(max_chunks, RF_MAX_CHUNKS)
    chunk_chars = _coerce_positive_int(chunk_chars, RF_CHUNK_CHARS)

    total_capacity = max_chunks * chunk_chars
    default_budget = total_capacity - RF_RESPONSE_HEADROOM_CHARS
    if default_budget < chunk_chars:
        default_budget = total_capacity

    budget = _coerce_positive_int(max_output_chars, default_budget)
    budget = min(budget, total_capacity)

    txt = _normalize_text(text)
    if not txt:
        txt = "No output."

    if len(txt) > budget:
        clipped = txt[:budget].rstrip()
        if " " in clipped:
            clipped = clipped.rsplit(" ", 1)[0].rstrip()
        txt = clipped or txt[:budget].rstrip()

    chunks = _chunk_text_words(txt, chunk_chars=chunk_chars, max_chunks=max_chunks)
    return chunks if chunks else ["No output."]


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _redis_key(name: str) -> str:
    return f"{REDIS_PREFIX}:{name}"


def redis_connect() -> Optional[redis.Redis]:
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        print(f"redis unavailable: {exc}", flush=True)
        return None


def redis_hset(name: str, mapping: dict, ttl_seconds: Optional[int] = None):
    if REDIS is None:
        return
    key = _redis_key(name)
    try:
        REDIS.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in mapping.items()})
        REDIS.expire(key, int(ttl_seconds or REDIS_TTL_SECONDS))
    except Exception:
        pass


def redis_set_json(name: str, value: Any, ttl_seconds: Optional[int] = None):
    if REDIS is None:
        return
    key = _redis_key(name)
    try:
        REDIS.set(key, _json_dumps(value if isinstance(value, dict) else {"value": value}), ex=int(ttl_seconds or REDIS_TTL_SECONDS))
    except Exception:
        pass


def redis_get_json(name: str, default=None):
    if REDIS is None:
        return default
    key = _redis_key(name)
    try:
        raw = REDIS.get(key)
        if raw is None:
            return default
        return json.loads(raw)
    except Exception:
        return default


def redis_setnx(name: str, value: str, ttl_seconds: int) -> bool:
    if REDIS is None:
        return True
    key = _redis_key(name)
    try:
        created = REDIS.set(key, value, nx=True, ex=max(1, int(ttl_seconds)))
        return bool(created)
    except Exception:
        return True


def metric_inc(name: str, amount: int = 1):
    if REDIS is None:
        return
    try:
        REDIS.incrby(_redis_key(f"metrics:{name}"), int(amount))
        REDIS.expire(_redis_key(f"metrics:{name}"), REDIS_TTL_SECONDS * 7)
    except Exception:
        pass


def _normalize_node_id_text(node_id: Any) -> Optional[str]:
    if node_id is None:
        return None
    text = str(node_id).strip().lower()
    if not text:
        return None
    if text.startswith("!"):
        raw = text[1:]
        try:
            return f"!{int(raw, 16):08x}"
        except ValueError:
            return text
    if text.startswith("0x"):
        try:
            return f"!{int(text, 16):08x}"
        except ValueError:
            return text
    if text.isdigit():
        try:
            return f"!{int(text):08x}"
        except ValueError:
            return text
    return text


def _safe_slug(value: str, fallback: str = "default") -> str:
    txt = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower())
    txt = re.sub(r"-{2,}", "-", txt).strip("-.")
    return txt or fallback


def _extract_links(text: str):
    links = []
    for m in re.finditer(r"https?://\S+", str(text or ""), flags=re.IGNORECASE):
        link = m.group(0).rstrip(").,;]\"'")
        if link:
            links.append(link)
    return links


def _dir_size_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for p in root.rglob("*"):
        try:
            if p.is_file():
                total += int(p.stat().st_size)
        except Exception:
            continue
    return total


def _library_thresholds():
    values = []
    for token in str(LIBRARY_THRESHOLD_BYTES_RAW).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except Exception:
            continue
    values = sorted(set(v for v in values if v > 0))
    return values


def _hq_ensure_layout():
    for p in (HQ_ROOT, HQ_LIBRARY_ROOT, HQ_OFFICES_ROOT, HQ_DESKS_ROOT):
        p.mkdir(parents=True, exist_ok=True)


def _expert_allowlist() -> set[str]:
    allowed = set()
    for node in EXPERT_ALLOWLIST_NODE_IDS_RAW:
        n = _normalize_node_id_text(node)
        if n:
            allowed.add(n)
    return allowed


def _expert_flow_key(env: dict) -> Optional[str]:
    sender = env.get("sender") if isinstance(env.get("sender"), dict) else {}
    node_id = _normalize_node_id_text(sender.get("node_id"))
    fp = str(env.get("channel_fingerprint") or "").strip().lower()
    if not node_id or not fp:
        return None
    return f"{node_id}:{fp}"


def _expert_flow_load(env: dict) -> Optional[dict]:
    key = _expert_flow_key(env)
    if not key:
        return None
    flow = redis_get_json(f"expert_flow:{key}", None)
    return flow if isinstance(flow, dict) else None


def _expert_flow_save(env: dict, flow: dict):
    key = _expert_flow_key(env)
    if not key:
        return
    redis_set_json(f"expert_flow:{key}", flow, ttl_seconds=EXPERT_FLOW_TTL_SECONDS)


def _expert_flow_clear(env: dict):
    key = _expert_flow_key(env)
    if not key:
        return
    redis_set_json(f"expert_flow:{key}", {}, ttl_seconds=1)


def _is_become_expert_trigger(parsed: dict) -> bool:
    if str(parsed.get("requested_intent") or "").strip().lower() == "become_an_expert":
        return True
    text = _extract_user_request(parsed.get("text") or "")
    return bool(EXPERT_TRIGGER_RE.search(text))


def _library_ingest_paused() -> bool:
    state = redis_get_json("library_ingest_state", {"paused": False})
    if not isinstance(state, dict):
        return False
    return _state_bool(state.get("paused"), False)


def _set_library_ingest_paused(paused: bool):
    redis_set_json("library_ingest_state", {"paused": bool(paused), "ts": ts_now()}, ttl_seconds=REDIS_TTL_SECONDS * 30)


def _emit_library_usage_events(client: mqtt.Client):
    used = _dir_size_bytes(HQ_LIBRARY_ROOT)
    thresholds = _library_thresholds()
    state = redis_get_json("library_threshold_state", {"index": -1})
    if not isinstance(state, dict):
        state = {"index": -1}
    idx = int(state.get("index", -1))

    next_idx = idx
    for i, threshold in enumerate(thresholds):
        if used >= threshold:
            next_idx = i
    if next_idx > idx and next_idx >= 0:
        emit_policy_event(
            client,
            "library_threshold_crossed",
            used_bytes=used,
            threshold_bytes=thresholds[next_idx],
            threshold_index=next_idx,
        )
        redis_set_json("library_threshold_state", {"index": next_idx, "used_bytes": used, "ts": ts_now()}, ttl_seconds=REDIS_TTL_SECONDS * 30)

    paused = _library_ingest_paused()
    if used >= LIBRARY_CAP_BYTES and not paused:
        _set_library_ingest_paused(True)
        emit_policy_event(client, "library_cap_reached_paused", used_bytes=used, cap_bytes=LIBRARY_CAP_BYTES)
    elif paused and used < int(LIBRARY_CAP_BYTES * 0.95):
        _set_library_ingest_paused(False)
        emit_policy_event(client, "library_ingest_resumed", used_bytes=used, cap_bytes=LIBRARY_CAP_BYTES)


def _persist_expertise_bundle(client: mqtt.Client, env: dict, flow: dict) -> tuple[bool, str]:
    _hq_ensure_layout()
    _emit_library_usage_events(client)

    if _library_ingest_paused():
        return False, "Library ingest is paused at cap. Free space and retry become_an_expert."

    target_agent = str(flow.get("target_agent") or EXPERT_AGENT_DEFAULT).strip() or EXPERT_AGENT_DEFAULT
    resources = [str(x).strip() for x in (flow.get("resources") or []) if str(x).strip()]
    if not resources:
        return False, "No links captured yet. Paste at least one link before typing end."

    if len(resources) > 200:
        resources = resources[:200]

    agent_slug = _safe_slug(target_agent, fallback="agent")
    expertise_id = f"xp-{ts_now()}-{uuid.uuid4().hex[:6]}"

    library_dir = HQ_LIBRARY_ROOT / "expertises" / agent_slug / expertise_id
    office_dir = HQ_OFFICES_ROOT / agent_slug
    desk_dir = HQ_DESKS_ROOT / agent_slug
    library_dir.mkdir(parents=True, exist_ok=True)
    office_dir.mkdir(parents=True, exist_ok=True)
    desk_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "expertise_id": expertise_id,
        "target_agent": target_agent,
        "target_agent_slug": agent_slug,
        "created_ts": ts_now(),
        "sender": env.get("sender"),
        "channel_fingerprint": env.get("channel_fingerprint"),
        "channel_name": env.get("channel_name"),
        "resources": resources,
        "resource_count": len(resources),
        "budget_bytes": int(EXPERT_BUDGET_BYTES),
        "status": "promoted",
    }

    manifest_path = library_dir / "manifest.json"
    manifest_path.write_text(_json_dumps(manifest), encoding="utf-8")

    index_path = office_dir / "expertise-index.ndjson"
    with index_path.open("a", encoding="utf-8") as f:
        f.write(_json_dumps(manifest) + "\n")

    desk_path = desk_dir / "active-expertise.json"
    desk_path.write_text(
        _json_dumps(
            {
                "updated_ts": ts_now(),
                "active_expertise_id": expertise_id,
                "target_agent": target_agent,
                "manifest_path": str(manifest_path),
                "resource_count": len(resources),
            }
        ),
        encoding="utf-8",
    )

    emit_policy_event(
        client,
        "expert_ingest_promoted",
        expertise_id=expertise_id,
        target_agent=target_agent,
        resource_count=len(resources),
        manifest_path=str(manifest_path),
    )
    _emit_library_usage_events(client)
    return True, f"Expertise bundle {expertise_id} promoted for {target_agent} with {len(resources)} resources."


def _handle_become_expert_query(client: mqtt.Client, env: dict, parsed: dict) -> Optional[str]:
    flow = _expert_flow_load(env)
    trigger = _is_become_expert_trigger(parsed)
    active = bool(flow and str(flow.get("stage") or "").strip())
    if not trigger and not active:
        return None

    sender = env.get("sender") if isinstance(env.get("sender"), dict) else {}
    sender_node = _normalize_node_id_text(sender.get("node_id"))
    allowed = _expert_allowlist()
    if not sender_node or sender_node not in allowed:
        emit_policy_event(
            client,
            "expert_ingest_failed",
            reason="unauthorized_sender",
            sender=sender,
        )
        return "Become-an-expert is restricted to approved operators on the allowlist."

    text = _extract_user_request(parsed.get("text") or "")
    low = text.lower().strip()

    if not active:
        flow = {
            "stage": "await_agent",
            "resources": [],
            "started_ts": ts_now(),
            "updated_ts": ts_now(),
        }
        _expert_flow_save(env, flow)
        emit_policy_event(client, "expert_ingest_started", sender=sender)
        return "Become-an-expert started. Which agent needs to become an expert?"

    stage = str(flow.get("stage") or "").strip().lower()
    if low in {"cancel", "stop"}:
        _expert_flow_clear(env)
        emit_policy_event(client, "expert_ingest_failed", reason="canceled_by_operator", sender=sender)
        return "Become-an-expert canceled."

    if stage == "await_agent":
        if not text or trigger:
            return "Which agent needs to become an expert?"
        target_agent = text[:80].strip() or EXPERT_AGENT_DEFAULT
        flow["target_agent"] = target_agent
        flow["stage"] = "collect_links"
        flow["resources"] = []
        flow["updated_ts"] = ts_now()
        _expert_flow_save(env, flow)
        return f"Target agent set to {target_agent}. Paste a resource link or type end when finished."

    if stage == "collect_links":
        resources = [str(x).strip() for x in (flow.get("resources") or []) if str(x).strip()]
        if low == "end":
            emit_policy_event(
                client,
                "expert_ingest_staged",
                target_agent=flow.get("target_agent") or EXPERT_AGENT_DEFAULT,
                resource_count=len(resources),
            )
            ok, message = _persist_expertise_bundle(client, env, flow)
            if ok:
                _expert_flow_clear(env)
                return message
            emit_policy_event(client, "expert_ingest_failed", reason="persist_failed", detail=message)
            return message

        links = _extract_links(text)
        if not links:
            return "Send an http/https resource link, or type end when you are done."

        known = set(resources)
        added = 0
        for link in links:
            if link in known:
                continue
            resources.append(link)
            known.add(link)
            added += 1
            if len(resources) >= 200:
                break

        flow["resources"] = resources
        flow["updated_ts"] = ts_now()
        _expert_flow_save(env, flow)
        return f"Added {added} link(s). Total resources: {len(resources)}. Paste another link or type end."

    _expert_flow_clear(env)
    return "Become-an-expert state was reset. Say 'become expert' to start again."


def _is_expert_query_candidate(parsed: dict, env: dict) -> bool:
    if _is_become_expert_trigger(parsed):
        return True
    flow = _expert_flow_load(env)
    return bool(flow and str(flow.get("stage") or "").strip())


def process_expert_query_request(client: mqtt.Client, env: dict, parsed: dict):
    started = time.time()
    engine = "real-joe-expert"
    try:
        emit_progress(client, env, "started", engine=engine)
        reply = _handle_become_expert_query(client, env, parsed)
        if reply is None:
            reply = "No expert action taken."

        chunks = bounded_chunks(
            reply,
            max_chunks=parsed.get("rf_max_chunks") if isinstance(parsed, dict) else None,
            chunk_chars=parsed.get("rf_chunk_chars") if isinstance(parsed, dict) else None,
            max_output_chars=parsed.get("max_output_chars") if isinstance(parsed, dict) else None,
        )

        inter_chunk_delay = max(1.0, _coerce_positive_float(MIN_INTER_CHUNK_DELAY_SECONDS, 1.0))
        initial_delay = max(0.0, _coerce_positive_float(INITIAL_RESPONSE_DELAY_SECONDS, 0.0))
        if initial_delay > 0:
            time.sleep(initial_delay)

        for idx, chunk in enumerate(chunks, start=1):
            payload = _with_optional_fields(
                {
                    "ts": ts_now(),
                    **env,
                    "text": chunk,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                },
                engine=engine,
                tool_run_id=None,
            )
            publish_json(client, REPLY_TOPIC, payload)
            if inter_chunk_delay > 0 and idx < len(chunks):
                time.sleep(inter_chunk_delay)

        elapsed_ms = int((time.time() - started) * 1000)
        redis_hset(
            f"request:{env['request_id']}",
            {
                "state": "completed",
                "completed_ts": ts_now(),
                "total_ms": elapsed_ms,
                "engine": engine,
            },
        )
        redis_set_json(
            f"terminal:{env['request_id']}",
            {"status": "completed", "completed_ts": ts_now(), "engine": engine},
        )
        emit_progress(
            client,
            env,
            "completed",
            engine=engine,
            total_ms=elapsed_ms,
            process_ms=elapsed_ms,
            queue_ms=0,
        )
    except Exception as exc:
        emit_error(client, env, str(exc), engine=engine, error_code="EXPERT_FLOW_FAILURE")
        redis_hset(
            f"request:{env['request_id']}",
            {
                "state": "error",
                "error": str(exc),
                "failed_ts": ts_now(),
            },
        )


def _state_bool(value: Any, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "on"}


def get_safety_state() -> dict:
    defaults = {
        "global_paused": GLOBAL_PAUSED_DEFAULT,
        "tools_paused": TOOLS_PAUSED_DEFAULT,
        "escalation_paused": ESCALATION_PAUSED_DEFAULT,
    }
    current = redis_get_json("safety_state", defaults)
    if not isinstance(current, dict):
        current = defaults.copy()
    return {
        "global_paused": _state_bool(current.get("global_paused"), defaults["global_paused"]),
        "tools_paused": _state_bool(current.get("tools_paused"), defaults["tools_paused"]),
        "escalation_paused": _state_bool(current.get("escalation_paused"), defaults["escalation_paused"]),
    }


def set_safety_state(new_state: dict):
    current = get_safety_state()
    merged = {
        "global_paused": _state_bool(new_state.get("global_paused"), current["global_paused"]),
        "tools_paused": _state_bool(new_state.get("tools_paused"), current["tools_paused"]),
        "escalation_paused": _state_bool(new_state.get("escalation_paused"), current["escalation_paused"]),
    }
    redis_set_json("safety_state", merged, ttl_seconds=REDIS_TTL_SECONDS * 30)
    return merged


def publish_json(client: mqtt.Client, topic: str, payload: dict):
    client.publish(topic, _json_dumps(payload), qos=0, retain=False)


def emit_policy_event(client: mqtt.Client, decision: str, **extra):
    payload = {
        "ts": ts_now(),
        "decision": str(decision),
        "engine": "real-joe",
    }
    payload.update(extra)
    publish_json(client, POLICY_EVENT_TOPIC, payload)


def _engine_name(use_openclaw: bool) -> str:
    if use_openclaw:
        return "openclaw"
    if OLLAMA_DIRECT_ENABLED:
        return "ollama-direct"
    return "real-joe-local"


def _openclaw_circuit_snapshot() -> dict:
    with OPENCLAW_CIRCUIT_LOCK:
        return dict(OPENCLAW_CIRCUIT)


def _openclaw_circuit_allow(now_ts: Optional[int] = None) -> bool:
    if not OPENCLAW_ENABLED:
        return False
    now_ts = int(now_ts or ts_now())
    with OPENCLAW_CIRCUIT_LOCK:
        return now_ts >= int(OPENCLAW_CIRCUIT.get("open_until", 0))


def _openclaw_circuit_mark_success():
    with OPENCLAW_CIRCUIT_LOCK:
        OPENCLAW_CIRCUIT["fails"] = 0
        OPENCLAW_CIRCUIT["last_error"] = ""


def _openclaw_circuit_mark_failure(reason: str) -> bool:
    now_ts = ts_now()
    opened = False
    with OPENCLAW_CIRCUIT_LOCK:
        open_until = int(OPENCLAW_CIRCUIT.get("open_until", 0))
        if now_ts < open_until:
            return False
        fails = int(OPENCLAW_CIRCUIT.get("fails", 0)) + 1
        OPENCLAW_CIRCUIT["fails"] = fails
        OPENCLAW_CIRCUIT["last_error"] = _normalize_text(reason)
        if fails >= OPENCLAW_CIRCUIT_FAIL_THRESHOLD:
            OPENCLAW_CIRCUIT["open_until"] = now_ts + OPENCLAW_CIRCUIT_OPEN_SECONDS
            OPENCLAW_CIRCUIT["fails"] = 0
            OPENCLAW_CIRCUIT["opened_count"] = int(OPENCLAW_CIRCUIT.get("opened_count", 0)) + 1
            opened = True
    return opened


def make_envelope(parsed: dict, request_id: str):
    sender = parsed.get("sender") if isinstance(parsed.get("sender"), dict) else {"node_id": parsed.get("sender")}
    sender_obj = {
        "node_id": sender.get("node_id"),
        "shortname": sender.get("shortname"),
        "longname": sender.get("longname"),
    }
    try:
        channel_index = int(parsed.get("channel_index") or 0)
    except Exception:
        channel_index = 0

    return {
        "request_id": request_id,
        "session_id": str(parsed.get("session_id") or f"sess-{request_id}"),
        "sender": sender_obj,
        "channel_index": channel_index,
        "channel_fingerprint": str(parsed.get("channel_fingerprint") or "").strip().lower() or None,
        "channel_name": str(parsed.get("channel_name") or "").strip() or None,
        "origin": str(parsed.get("origin") or "meshtastic"),
        "created_ts": int(parsed.get("created_ts") or ts_now()),
        "expires_ts": int(parsed.get("expires_ts") or (ts_now() + 180)),
        "trace": parsed.get("trace") or {"control_host": "susnet", "version": "real-joe-v1"},
    }


def _with_optional_fields(payload: dict, engine: str, tool_run_id: Optional[str], error_code: Optional[str] = None):
    out = dict(payload)
    out["engine"] = engine
    out["tool_run_id"] = tool_run_id
    out["safety_state"] = get_safety_state()
    if error_code:
        out["error_code"] = error_code
    return out


def emit_ack(client: mqtt.Client, env: dict, engine: str, tool_run_id: Optional[str] = None):
    payload = _with_optional_fields({"ts": ts_now(), **env, "status": "accepted"}, engine=engine, tool_run_id=tool_run_id)
    publish_json(client, ACK_TOPIC, payload)


def emit_progress(client: mqtt.Client, env: dict, stage: str, engine: str, tool_run_id: Optional[str] = None, **extra):
    payload = _with_optional_fields({"ts": ts_now(), **env, "stage": stage}, engine=engine, tool_run_id=tool_run_id)
    payload.update(extra)
    publish_json(client, PROGRESS_TOPIC, payload)


def emit_error(client: mqtt.Client, env: dict, error: str, engine: str, tool_run_id: Optional[str] = None, error_code: str = "UNSPECIFIED", **extra):
    payload = _with_optional_fields({"ts": ts_now(), **env, "error": str(error)}, engine=engine, tool_run_id=tool_run_id, error_code=error_code)
    payload.update(extra)
    publish_json(client, ERROR_TOPIC, payload)


def emit_dlq(client: mqtt.Client, reason: str, raw_payload: Any, topic: str):
    publish_json(
        client,
        DLQ_TOPIC,
        {
            "ts": ts_now(),
            "reason": str(reason),
            "topic": topic,
            "payload": raw_payload,
            "engine": "real-joe",
            "error_code": "DLQ",
        },
    )


def _extract_user_request(text: str) -> str:
    raw = str(text or "")
    marker = "RF output constraints:"
    if marker in raw:
        raw = raw.split(marker, 1)[0]
    return _normalize_text(raw)


def _joe_persona_prompt(user_text: str) -> str:
    clean = _normalize_text(user_text)
    if not clean:
        clean = "Reply concisely."
    return (
        "You are Joe, the assistant behind Mr. Pink on a Meshtastic bridge. "
        "Reply in plain, concise English with practical mesh-operations focus. "
        "Never mention model names, vendors, or internal runtime details. "
        "Never say you are Qwen or any model identity. "
        "Do not refuse with generic 'no realtime data' language; instead provide the best operational answer and one concrete next step when uncertain.\n"
        f"User request: {clean}\n"
        "Joe:"
    )


def _safe_arithmetic_reply(text: str) -> Optional[str]:
    t = _normalize_text(text).lower().rstrip("?")
    m = re.match(r"^(?:what\s+is\s+|calculate\s+|compute\s+)?(-?\d+)\s*([+\-*/])\s*(-?\d+)$", t)
    if not m:
        return None
    a = int(m.group(1))
    op = m.group(2)
    b = int(m.group(3))
    if op == "+":
        return str(a + b)
    if op == "-":
        return str(a - b)
    if op == "*":
        return str(a * b)
    if op == "/":
        if b == 0:
            return "Division by zero is undefined."
        val = a / b
        return str(int(val)) if val.is_integer() else f"{val:.6g}"
    return None


def _fallback_local_reply(text: str) -> str:
    user_text = _extract_user_request(text)
    arithmetic = _safe_arithmetic_reply(user_text)
    if arithmetic is not None:
        return arithmetic

    t = user_text.lower().strip()
    if re.search(r"\b(hello|hi|hey|yo)\b", t):
        return "Hello. I am online in controlled fallback mode while escalation is paused or unavailable."
    if re.search(r"\b(help|what can you do)\b", t):
        return "I can answer concise mesh questions and status checks while escalation is unavailable."
    if re.search(r"\b(status|online|alive)\b", t):
        return "I am online. Escalation path state is controlled by the safety switchboard."
    return (
        "I am in safe fallback mode right now. I can still provide short operational replies. "
        "Try a concise question."
    )


def _sanitize_agent_reply(reply_text: str, user_text: str, request_mode: str) -> Tuple[str, Optional[str]]:
    clean = _normalize_text(reply_text)
    user_clean = _normalize_text(user_text)
    if not clean:
        return _fallback_local_reply(user_text), "empty_reply"

    # Bridge layer owns speaker labels; strip any upstream labels.
    clean = re.sub(r"^\s*(joe|mr\.?\s*pink|assistant)\s*[:\-]\s*", "", clean, flags=re.IGNORECASE)
    clean = _normalize_text(clean)
    if not clean:
        return _fallback_local_reply(user_text), "empty_after_label_strip"

    lower = clean.lower()
    disallowed = [
        r"\bas an ai\b",
        r"\blanguage model\b",
        r"\bi am qwen\b",
        r"\bqwen\b",
        r"\balibaba cloud\b",
        r"\bi do not have real[- ]?time data\b",
        r"\bi don't have real[- ]?time data\b",
    ]
    for pattern in disallowed:
        if re.search(pattern, lower):
            if request_mode == "function":
                return (
                    "I can still help with this request. For live mesh state, ask for activity summary, traffic load, or nodes in range.",
                    "model_identity_or_generic_disclaimer",
                )
            return _fallback_local_reply(user_text), "model_identity_or_generic_disclaimer"

    refusal_patterns = [
        r"\bi can't assist with that\b",
        r"\bi cannot assist with that\b",
        r"\bi can't help with that\b",
        r"\bi cannot help with that\b",
        r"^i'?m sorry,\s*but\b",
    ]
    if any(re.search(pattern, lower) for pattern in refusal_patterns):
        user_lower = user_clean.lower()
        if re.search(r"\b(nodes?|online|in range|who is around)\b", user_lower):
            return (
                "I can help with that. Ask for nodes in range or activity summary and I will return the current mesh snapshot.",
                "generic_refusal_rewritten",
            )
        if re.search(r"\b(traffic|load|busy|volume)\b", user_lower):
            return (
                "I can help with traffic view. Ask for traffic load and I will return a concise current summary.",
                "generic_refusal_rewritten",
            )
        return (
            "I can help with concise mesh operations guidance. Ask a specific question and I will answer directly.",
            "generic_refusal_rewritten",
        )

    if user_clean and lower == user_clean.lower():
        return (
            "Received. Ask a concise mesh question and I will answer directly.",
            "echoed_user_input",
        )

    return clean, None


def _extract_json_from_text(text: str) -> Optional[dict]:
    text = str(text or "").strip()
    if not text:
        return None
    # Handle leading diagnostics by carving out the final JSON object.
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    chunk = text[first : last + 1]
    try:
        return json.loads(chunk)
    except Exception:
        return None


def _run_subprocess_with_cancel(cmd: list[str], cancel_event: threading.Event, timeout_seconds: int) -> Tuple[int, str, str, bool]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start = time.time()
    terminated_by_cancel = False

    while proc.poll() is None:
        if cancel_event.is_set():
            terminated_by_cancel = True
            proc.terminate()
            break
        if time.time() - start > timeout_seconds:
            proc.terminate()
            break
        time.sleep(0.2)

    try:
        out, err = proc.communicate(timeout=5)
    except Exception:
        proc.kill()
        out, err = proc.communicate()

    rc = proc.returncode if proc.returncode is not None else 1
    return rc, out or "", err or "", terminated_by_cancel


def _openclaw_gateway_call(method: str, params: dict, cancel_event: threading.Event) -> dict:
    if method == "agent.wait":
        gateway_timeout_ms = int(OPENCLAW_WAIT_TIMEOUT_MS)
    else:
        gateway_timeout_ms = max(5000, int(OPENCLAW_AGENT_TIMEOUT_SECONDS) * 1000 + 5000)

    cmd = [
        "docker",
        "exec",
        OPENCLAW_GATEWAY_CONTAINER,
        "node",
        "/app/openclaw.mjs",
        "gateway",
        "call",
        method,
        "--params",
        _json_dumps(params),
        "--timeout",
        str(max(5000, int(gateway_timeout_ms))),
        "--json",
    ]
    rc, out, err, canceled = _run_subprocess_with_cancel(cmd, cancel_event, OPENCLAW_CALL_TIMEOUT_SECONDS)
    if canceled:
        raise RuntimeError("CANCELED")
    if rc != 0:
        message = _normalize_text(err) or _normalize_text(out) or f"gateway call rc={rc}"
        raise RuntimeError(message)
    parsed = _extract_json_from_text(out)
    if not isinstance(parsed, dict):
        raise RuntimeError("gateway_json_parse_failed")
    return parsed


def _extract_result_text(agent_payload: dict) -> Optional[str]:
    result = agent_payload.get("result") if isinstance(agent_payload, dict) else None
    if not isinstance(result, dict):
        return None
    payloads = result.get("payloads")
    if not isinstance(payloads, list):
        return None
    texts = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        txt = _normalize_text(item.get("text") or "")
        if txt:
            texts.append(txt)
    if not texts:
        return None
    return "\n".join(texts)


def _clean_cli_text(text: str) -> str:
    s = str(text or "")
    s = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", s)
    s = s.replace("\r", "\n")
    # Strip braille spinner glyphs if present.
    s = re.sub(r"[\u2800-\u28FF]", " ", s)
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    return _normalize_text(" ".join(lines))


def _ollama_base_url() -> Optional[str]:
    if OLLAMA_URL:
        return OLLAMA_URL.rstrip("/")

    now = ts_now()
    cached_url = OLLAMA_IP_CACHE.get("url")
    cached_ts = int(OLLAMA_IP_CACHE.get("ts", 0))
    if cached_url and (now - cached_ts) <= OLLAMA_IP_CACHE_SECONDS:
        return str(cached_url)

    try:
        proc = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                OLLAMA_CONTAINER,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=4,
        )
        ip = proc.stdout.strip()
        if ip:
            url = f"http://{ip}:11434"
            OLLAMA_IP_CACHE["url"] = url
            OLLAMA_IP_CACHE["ts"] = now
            return url
    except Exception:
        return None
    return None


def run_ollama_direct_query(parsed: dict, cancel_event: threading.Event) -> str:
    if cancel_event.is_set():
        raise RuntimeError("CANCELED")
    prompt = _joe_persona_prompt(_extract_user_request(parsed.get("text") or ""))
    base = _ollama_base_url()
    if not base:
        raise RuntimeError("ollama_unreachable")

    max_output_chars = _coerce_positive_int(parsed.get("max_output_chars"), RF_MAX_CHUNKS * RF_CHUNK_CHARS)
    max_predict = max(24, min(160, int(max_output_chars / 4)))

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "20m",
        "options": {
            "num_predict": max_predict,
            "temperature": 0.1,
        },
    }

    req = Request(
        f"{base}/api/generate",
        data=_json_dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=max(5, int(OLLAMA_TIMEOUT_SECONDS))) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"ollama_http_error:{exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"ollama_http_error:{exc}") from exc

    if cancel_event.is_set():
        raise RuntimeError("CANCELED")

    try:
        obj = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"ollama_json_parse_failed:{exc}") from exc

    txt = _normalize_text(obj.get("response") or "")
    if not txt:
        raise RuntimeError("ollama_empty_output")
    return txt


def run_openclaw_query(parsed: dict, request_id: str, cancel_event: threading.Event) -> Tuple[str, Optional[str]]:
    session_id = str(parsed.get("session_id") or f"sess-{request_id}")
    message = _extract_user_request(parsed.get("text") or "")

    params = {
        "message": message,
        "sessionId": session_id,
        "idempotencyKey": request_id,
        "timeout": int(OPENCLAW_AGENT_TIMEOUT_SECONDS),
    }
    if OPENCLAW_EXTRA_SYSTEM_PROMPT:
        params["extraSystemPrompt"] = OPENCLAW_EXTRA_SYSTEM_PROMPT

    accepted = _openclaw_gateway_call("agent", params, cancel_event)
    status = str(accepted.get("status") or "").lower()
    run_id = str(accepted.get("runId") or "").strip() or None

    accepted_txt = _extract_result_text(accepted)
    if accepted_txt:
        return accepted_txt, run_id
    if status == "error":
        raise RuntimeError(str(accepted.get("summary") or accepted.get("error") or "agent_error"))

    if run_id:
        if cancel_event.is_set():
            raise RuntimeError("CANCELED")
        wait_params = {"runId": run_id, "timeoutMs": int(OPENCLAW_WAIT_TIMEOUT_MS)}
        wait_resp = _openclaw_gateway_call("agent.wait", wait_params, cancel_event)
        wait_status = str(wait_resp.get("status") or "").lower()

        wait_txt = _extract_result_text(wait_resp)
        if wait_txt:
            return wait_txt, run_id
        if wait_status == "error":
            raise RuntimeError(str(wait_resp.get("error") or wait_resp.get("summary") or "agent_wait_error"))
        if wait_status == "timeout":
            raise RuntimeError("agent_timeout")

        summary = _normalize_text(wait_resp.get("summary") or wait_resp.get("message") or "")
        if summary and wait_status in {"completed", "done", "ok", "success"}:
            return summary, run_id
        raise RuntimeError("agent_no_result")

    # No run id returned: bounded status poll via agent endpoint only.
    for _ in range(max(1, OPENCLAW_POLL_COUNT)):
        if cancel_event.is_set():
            raise RuntimeError("CANCELED")
        latest = _openclaw_gateway_call("agent", params, cancel_event)
        latest_status = str(latest.get("status") or "").lower()
        txt = _extract_result_text(latest)
        if txt:
            return txt, run_id
        if latest_status == "error":
            raise RuntimeError(str(latest.get("summary") or latest.get("error") or "agent_error"))
        if latest_status == "timeout":
            raise RuntimeError("agent_timeout")

    raise RuntimeError("agent_timeout")


def _still_working_loop(client: mqtt.Client, env: dict, done_event: threading.Event, engine_holder: dict, tool_run_id_holder: dict):
    while not done_event.wait(STILL_WORKING_INTERVAL_SECONDS):
        live_engine = str(engine_holder.get("value") or "real-joe-local")
        emit_progress(
            client,
            env,
            "still_working",
            engine=live_engine,
            tool_run_id=tool_run_id_holder.get("value"),
        )


def _request_rollout_path(env: dict) -> str:
    mode = ROLL_OUT_MODE
    fp = str(env.get("channel_fingerprint") or "").strip().lower()

    if mode == "full":
        return "openclaw"

    if mode == "dedicated":
        if PILOT_CHANNEL_FINGERPRINTS and fp in PILOT_CHANNEL_FINGERPRINTS:
            return "openclaw"
        return "fallback"

    if mode == "canary":
        if PILOT_CHANNEL_FINGERPRINTS and fp in PILOT_CHANNEL_FINGERPRINTS:
            return "openclaw"
        # Stable bucket by request_id for deterministic canary behavior.
        rid = str(env.get("request_id") or "")
        bucket = (sum(ord(c) for c in rid) % 100) if rid else 0
        return "openclaw" if bucket < CANARY_PERCENT else "fallback"

    return "fallback"


def _request_execution_mode(parsed: dict) -> str:
    mode = str((parsed or {}).get("execution_mode") or "chat_only").strip().lower()
    return "function" if mode == "function" else "chat_only"


def process_query_request(client: mqtt.Client, env: dict, parsed: dict, cancel_event: threading.Event, done_event: threading.Event):
    started = time.time()
    tool_run_id_holder = {"value": None}

    request_mode = _request_execution_mode(parsed if isinstance(parsed, dict) else {})
    rollout_path = _request_rollout_path(env)
    safety = get_safety_state()
    openclaw_allowed = _openclaw_circuit_allow()
    use_openclaw = bool(
        openclaw_allowed
        and request_mode == "function"
        and rollout_path == "openclaw"
        and not safety.get("escalation_paused")
        and not safety.get("tools_paused")
    )
    if (
        request_mode == "function"
        and OPENCLAW_ENABLED
        and rollout_path == "openclaw"
        and not openclaw_allowed
    ):
        snap = _openclaw_circuit_snapshot()
        emit_policy_event(
            client,
            "openclaw_circuit_open",
            request_id=env.get("request_id"),
            open_until=snap.get("open_until"),
            last_error=snap.get("last_error"),
        )
    engine = _engine_name(use_openclaw)
    engine_holder = {"value": engine}

    redis_hset(
        f"request:{env['request_id']}",
        {
            "state": "started",
            "engine": engine,
            "sender": env.get("sender"),
                "channel_fingerprint": env.get("channel_fingerprint"),
                "channel_name": env.get("channel_name"),
                "created_ts": env.get("created_ts"),
                "started_ts": ts_now(),
                "execution_mode": request_mode,
            },
        )

    emit_progress(client, env, "started", engine=engine)
    worker = threading.Thread(
        target=_still_working_loop,
        args=(client, env, done_event, engine_holder, tool_run_id_holder),
        daemon=True,
    )
    worker.start()

    try:
        if cancel_event.is_set():
            emit_progress(client, env, "canceled", engine=engine)
            metric_inc("cancel_count")
            return

        text = parsed.get("text") if isinstance(parsed, dict) else ""
        max_output_chars = parsed.get("max_output_chars") if isinstance(parsed, dict) else None
        rf_chunk_chars = parsed.get("rf_chunk_chars") if isinstance(parsed, dict) else None
        rf_max_chunks = parsed.get("rf_max_chunks") if isinstance(parsed, dict) else None

        if use_openclaw:
            emit_progress(client, env, "openclaw_dispatch", engine=engine)
            try:
                reply, tool_run_id = run_openclaw_query(parsed, env["request_id"], cancel_event)
                _openclaw_circuit_mark_success()
                tool_run_id_holder["value"] = tool_run_id
                emit_progress(client, env, "openclaw_completed", engine=engine, tool_run_id=tool_run_id)
            except Exception as exc:
                metric_inc("tool_failure_rate")
                circuit_opened = _openclaw_circuit_mark_failure(str(exc))
                emit_policy_event(
                    client,
                    "openclaw_fallback_activated",
                    request_id=env.get("request_id"),
                    error=str(exc),
                )
                if circuit_opened:
                    snap = _openclaw_circuit_snapshot()
                    emit_policy_event(
                        client,
                        "openclaw_circuit_opened",
                        request_id=env.get("request_id"),
                        open_until=snap.get("open_until"),
                        last_error=snap.get("last_error"),
                    )

                if OLLAMA_DIRECT_ENABLED and not cancel_event.is_set():
                    engine_holder["value"] = "ollama-direct"
                    emit_progress(
                        client,
                        env,
                        "ollama_direct_dispatch",
                        engine="ollama-direct",
                        tool_run_id=tool_run_id_holder.get("value"),
                        reason=str(exc),
                    )
                    try:
                        reply = run_ollama_direct_query(parsed if isinstance(parsed, dict) else {}, cancel_event)
                        engine = "ollama-direct"
                        engine_holder["value"] = engine
                        emit_progress(
                            client,
                            env,
                            "ollama_direct_completed",
                            engine=engine,
                            tool_run_id=tool_run_id_holder.get("value"),
                        )
                    except Exception as ollama_exc:
                        emit_policy_event(
                            client,
                            "ollama_direct_fallback_activated",
                            request_id=env.get("request_id"),
                            error=str(ollama_exc),
                            upstream_error=str(exc),
                        )
                        emit_progress(
                            client,
                            env,
                            "fallback_activated",
                            engine="real-joe-local",
                            tool_run_id=tool_run_id_holder.get("value"),
                            reason=f"openclaw:{exc};ollama:{ollama_exc}",
                        )
                        engine = "real-joe-local"
                        engine_holder["value"] = engine
                        reply = _fallback_local_reply(text)
                else:
                    emit_progress(
                        client,
                        env,
                        "fallback_activated",
                        engine="real-joe-local",
                        tool_run_id=tool_run_id_holder.get("value"),
                        reason=str(exc),
                    )
                    engine = "real-joe-local"
                    engine_holder["value"] = engine
                    reply = _fallback_local_reply(text)
        else:
            if OLLAMA_DIRECT_ENABLED and not cancel_event.is_set():
                engine_holder["value"] = "ollama-direct"
                emit_progress(
                    client,
                    env,
                    "ollama_direct_dispatch",
                    engine="ollama-direct",
                    reason="openclaw_disabled_policy_or_circuit",
                )
                try:
                    reply = run_ollama_direct_query(parsed if isinstance(parsed, dict) else {}, cancel_event)
                    engine = "ollama-direct"
                    engine_holder["value"] = engine
                    emit_progress(
                        client,
                        env,
                        "ollama_direct_completed",
                        engine=engine,
                        tool_run_id=tool_run_id_holder.get("value"),
                    )
                except Exception as ollama_exc:
                    emit_policy_event(
                        client,
                        "ollama_direct_fallback_activated",
                        request_id=env.get("request_id"),
                        error=str(ollama_exc),
                        upstream_error="openclaw_disabled_or_policy",
                    )
                    emit_progress(
                        client,
                        env,
                        "fallback_activated",
                        engine="real-joe-local",
                        tool_run_id=tool_run_id_holder.get("value"),
                        reason=str(ollama_exc),
                    )
                    engine = "real-joe-local"
                    engine_holder["value"] = engine
                    reply = _fallback_local_reply(text)
            else:
                emit_progress(
                    client,
                    env,
                    "fallback_path",
                    engine=engine,
                    reason="rollout_or_safety_policy",
                )
                engine_holder["value"] = engine
                reply = _fallback_local_reply(text)

        if cancel_event.is_set():
            emit_progress(client, env, "canceled", engine=engine, tool_run_id=tool_run_id_holder.get("value"))
            metric_inc("cancel_count")
            return

        user_text = _extract_user_request(text)
        reply, sanitize_reason = _sanitize_agent_reply(reply, user_text=user_text, request_mode=request_mode)
        if sanitize_reason:
            emit_policy_event(
                client,
                "reply_sanitized",
                request_id=env.get("request_id"),
                reason=sanitize_reason,
                execution_mode=request_mode,
                engine=engine,
            )

        chunks = bounded_chunks(
            reply,
            max_chunks=rf_max_chunks,
            chunk_chars=rf_chunk_chars,
            max_output_chars=max_output_chars,
        )

        inter_chunk_delay = max(1.0, _coerce_positive_float(MIN_INTER_CHUNK_DELAY_SECONDS, 1.0))
        initial_delay = max(0.0, _coerce_positive_float(INITIAL_RESPONSE_DELAY_SECONDS, 0.0))
        if initial_delay > 0:
            time.sleep(initial_delay)

        for idx, chunk in enumerate(chunks, start=1):
            payload = _with_optional_fields(
                {
                    "ts": ts_now(),
                    **env,
                    "text": chunk,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                },
                engine=engine,
                tool_run_id=tool_run_id_holder.get("value"),
            )
            publish_json(client, REPLY_TOPIC, payload)
            emit_policy_event(
                client,
                "reply_chunk_published",
                request_id=env.get("request_id"),
                chunk_index=idx,
                chunk_count=len(chunks),
                engine=engine,
            )
            if inter_chunk_delay > 0 and idx < len(chunks):
                time.sleep(inter_chunk_delay)

        elapsed_ms = int((time.time() - started) * 1000)
        metric_inc("completion_count")
        redis_hset(
            f"request:{env['request_id']}",
            {
                "state": "completed",
                "completed_ts": ts_now(),
                "total_ms": elapsed_ms,
                "engine": engine,
                "tool_run_id": tool_run_id_holder.get("value"),
            },
        )
        redis_set_json(
            f"terminal:{env['request_id']}",
            {
                "status": "completed",
                "completed_ts": ts_now(),
                "engine": engine,
                "tool_run_id": tool_run_id_holder.get("value"),
            },
        )
        emit_progress(
            client,
            env,
            "completed",
            engine=engine,
            tool_run_id=tool_run_id_holder.get("value"),
            total_ms=elapsed_ms,
            process_ms=elapsed_ms,
            queue_ms=0,
        )
    except Exception as exc:
        metric_inc("error_count")
        redis_hset(
            f"request:{env['request_id']}",
            {
                "state": "error",
                "error": str(exc),
                "failed_ts": ts_now(),
            },
        )
        redis_set_json(
            f"terminal:{env['request_id']}",
            {"status": "error", "error": str(exc), "failed_ts": ts_now()},
        )
        emit_error(
            client,
            env,
            str(exc),
            engine=engine,
            tool_run_id=tool_run_id_holder.get("value"),
            error_code="ENGINE_FAILURE",
        )
    finally:
        done_event.set()
        with INFLIGHT_LOCK:
            INFLIGHT.pop(env["request_id"], None)


def _valid_required_keys(parsed: dict) -> Tuple[bool, str]:
    required = ["request_id", "session_id", "sender", "text", "channel_fingerprint", "channel_name"]
    for key in required:
        if key not in parsed:
            return False, f"missing_{key}"
    sender = parsed.get("sender")
    if not isinstance(sender, dict) or not sender.get("node_id"):
        return False, "invalid_sender"
    if not str(parsed.get("channel_fingerprint") or "").strip():
        return False, "missing_channel_fingerprint"
    if not str(parsed.get("channel_name") or "").strip():
        return False, "missing_channel_name"
    return True, "ok"


def _authorized_operator(parsed: dict) -> bool:
    if not OPERATOR_TOKEN:
        return False
    token = str(parsed.get("operator_token") or "").strip()
    return bool(token and token == OPERATOR_TOKEN)


def _handle_control(client: mqtt.Client, parsed: dict):
    action = str(parsed.get("action") or "").strip().lower()
    request_id = str(parsed.get("request_id") or "").strip()

    if action in {"pause_global", "resume_global", "pause_tools", "resume_tools", "pause_escalation", "resume_escalation", "set_safety", "soft_shutdown"}:
        if not _authorized_operator(parsed):
            env = make_envelope(parsed if isinstance(parsed, dict) else {}, request_id or f"ctl-{ts_now()}")
            emit_error(client, env, "operator authorization required", engine="real-joe", error_code="UNAUTHORIZED_OPERATOR")
            emit_policy_event(client, "switchboard_denied", action=action)
            return

    if action == "pause_global":
        state = set_safety_state({"global_paused": True})
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return
    if action == "resume_global":
        state = set_safety_state({"global_paused": False})
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return
    if action == "pause_tools":
        state = set_safety_state({"tools_paused": True})
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return
    if action == "resume_tools":
        state = set_safety_state({"tools_paused": False})
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return
    if action == "pause_escalation":
        state = set_safety_state({"escalation_paused": True})
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return
    if action == "resume_escalation":
        state = set_safety_state({"escalation_paused": False})
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return
    if action == "set_safety":
        desired = {
            "global_paused": parsed.get("global_paused"),
            "tools_paused": parsed.get("tools_paused"),
            "escalation_paused": parsed.get("escalation_paused"),
        }
        state = set_safety_state(desired)
        emit_policy_event(client, "safety_state_changed", action=action, safety_state=state)
        return

    if action == "soft_shutdown":
        confirm = str(parsed.get("confirm") or "").strip().upper()
        target = str(parsed.get("target") or "susnet").strip().lower()
        if confirm != "CONFIRM":
            emit_policy_event(client, "soft_shutdown_denied", reason="missing_confirm", target=target)
            return
        if not ENABLE_SOFT_SHUTDOWN:
            emit_policy_event(client, "soft_shutdown_denied", reason="feature_disabled", target=target)
            return
        if not SOFT_SHUTDOWN_COMMAND:
            emit_policy_event(client, "soft_shutdown_denied", reason="command_not_configured", target=target)
            return
        try:
            subprocess.Popen(SOFT_SHUTDOWN_COMMAND, shell=True)
            emit_policy_event(client, "soft_shutdown_issued", target=target)
        except Exception as exc:
            emit_policy_event(client, "soft_shutdown_failed", target=target, error=str(exc))
        return

    # Cancellation path.
    if action in {"cancel", "stop"} and request_id:
        with INFLIGHT_LOCK:
            inflight = INFLIGHT.get(request_id)
        env = (inflight or {}).get("env") or make_envelope(parsed if isinstance(parsed, dict) else {}, request_id)
        if not inflight:
            emit_error(client, env, "request_not_found", engine="real-joe", error_code="REQUEST_NOT_FOUND", stage="cancel")
            return
        inflight["cancel_event"].set()
        inflight["done_event"].set()
        emit_progress(client, env, "cancel_requested", engine="real-joe")
        emit_progress(client, env, "canceled", engine="real-joe")
        metric_inc("cancel_count")
        return

    if request_id and not action:
        # Backward-compatible cancel payloads with only request_id.
        with INFLIGHT_LOCK:
            inflight = INFLIGHT.get(request_id)
        env = (inflight or {}).get("env") or make_envelope(parsed if isinstance(parsed, dict) else {}, request_id)
        if not inflight:
            emit_error(client, env, "request_not_found", engine="real-joe", error_code="REQUEST_NOT_FOUND", stage="cancel")
            return
        inflight["cancel_event"].set()
        inflight["done_event"].set()
        emit_progress(client, env, "cancel_requested", engine="real-joe")
        emit_progress(client, env, "canceled", engine="real-joe")
        metric_inc("cancel_count")
        return

    emit_policy_event(client, "control_ignored", action=action or "none")


def on_connect(client, userdata, flags, rc, properties=None):  # type: ignore[override]
    print(f"MQTT connected rc={rc} to {BROKER_HOST}:{BROKER_PORT}", flush=True)
    if rc != 0:
        print("MQTT connect failed; will retry via loop", flush=True)
        return
    for topic, qos in SUB_TOPICS:
        client.subscribe(topic, qos=qos)
        print(f"subscribed {topic}", flush=True)


def on_disconnect(client, userdata, *args):  # type: ignore[override]
    rc = None
    if len(args) >= 2:
        # Callback API v2: disconnect_flags, reason_code, [properties]
        rc = args[1]
    elif len(args) >= 1:
        # Callback API v1: rc
        rc = args[0]
    print(f"MQTT disconnected rc={rc}", flush=True)


def on_message(client, userdata, msg):
    topic = msg.topic
    raw = msg.payload.decode("utf-8", errors="replace")

    if topic == CONTROL_TOPIC:
        try:
            parsed = json.loads(raw)
        except Exception:
            emit_dlq(client, "malformed_control", raw, topic)
            return
        if not isinstance(parsed, dict):
            emit_dlq(client, "non_object_control", raw, topic)
            return
        _handle_control(client, parsed)
        return

    if topic == QUERY_TOPIC:
        try:
            parsed = json.loads(raw)
        except Exception:
            emit_dlq(client, "malformed_query", raw, topic)
            return

        if not isinstance(parsed, dict):
            emit_dlq(client, "non_object_query", raw, topic)
            return

        request_id = str(parsed.get("request_id") or "").strip() or f"req-{ts_now()}"
        env = make_envelope(parsed, request_id)

        valid, reason = _valid_required_keys(parsed)
        if not valid:
            emit_error(client, env, reason, engine="real-joe", error_code="INVALID_CONTRACT")
            emit_dlq(client, reason, parsed, topic)
            metric_inc("invalid_contract")
            return

        safety = get_safety_state()
        if safety.get("global_paused"):
            emit_error(
                client,
                env,
                "global execution pause is active",
                engine="real-joe",
                error_code="GLOBAL_PAUSED",
            )
            emit_policy_event(client, "query_rejected_global_pause", request_id=request_id)
            metric_inc("global_pause_reject")
            return

        dedupe_claim = redis_setnx(f"dedupe:{request_id}", str(ts_now()), ttl_seconds=900)
        if not dedupe_claim:
            terminal = redis_get_json(f"terminal:{request_id}", None)
            emit_policy_event(
                client,
                "duplicate_request_ignored",
                request_id=request_id,
                terminal=terminal,
            )
            metric_inc("duplicate_reject")
            return

        rollout_path = _request_rollout_path(env)
        request_mode = _request_execution_mode(parsed)
        expert_candidate = _is_expert_query_candidate(parsed, env)

        initial_engine = "real-joe-expert" if expert_candidate else _engine_name(
            OPENCLAW_ENABLED and request_mode == "function" and rollout_path == "openclaw"
        )

        ack_ms = int((time.time() - float(msg.timestamp if hasattr(msg, "timestamp") else time.time())) * 1000)
        metric_inc("ack_count")
        redis_hset(
            f"request:{request_id}",
            {
                "state": "accepted",
                "request_id": request_id,
                "accepted_ts": ts_now(),
                "engine": initial_engine,
                "rollout_path": rollout_path,
                "execution_mode": request_mode,
                "ack_latency_ms": ack_ms,
            },
        )

        emit_ack(client, env, engine=initial_engine)
        emit_progress(client, env, "queued", engine=initial_engine, rollout_path=rollout_path)

        if expert_candidate:
            process_expert_query_request(client, env, parsed)
            return

        cancel_event = threading.Event()
        done_event = threading.Event()
        with INFLIGHT_LOCK:
            INFLIGHT[request_id] = {
                "cancel_event": cancel_event,
                "done_event": done_event,
                "started_ts": ts_now(),
                "env": env,
            }

        worker = threading.Thread(
            target=process_query_request,
            args=(client, env, parsed, cancel_event, done_event),
            daemon=True,
        )
        worker.start()
        return

    if topic.endswith("/rx"):
        try:
            payload = json.loads(raw)
        except Exception:
            return
        sender = payload.get("sender") or {}
        identity = sender.get("identity") if isinstance(sender, dict) else {}
        event = {
            "ts": int(payload.get("ts") or ts_now()),
            "channel_index": int(payload.get("channel_index") or 0),
            "channel_fingerprint": str(payload.get("channel_fingerprint") or "").strip().lower() or None,
            "channel_name": str(payload.get("channel_name") or "").strip() or None,
            "sender_name": (identity.get("longname") or identity.get("shortname") or identity.get("node_id") or "Unknown Node"),
        }
        with LOCK:
            RX_EVENTS.append(event)
            STATE["last_rx_ts"] = event["ts"]
        return

    if topic.endswith("/policy"):
        try:
            payload = json.loads(raw)
            decision = payload.get("decision")
        except Exception:
            decision = None
        if decision:
            with LOCK:
                POLICY_COUNTER[str(decision)] += 1
        return

    if topic.endswith("/health"):
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        with LOCK:
            STATE["health"] = payload
        return

    if topic.endswith("/nodes"):
        try:
            payload = json.loads(raw)
            nodes = payload.get("nodes") or []
        except Exception:
            nodes = []
        now = ts_now()
        with LOCK:
            for node in nodes:
                user = node.get("user") or {}
                node_id = node.get("node_id") or f"unknown-{now}"
                STATE["nodes"][str(node_id)] = {
                    "identity": {
                        "node_id": node.get("node_id"),
                        "shortname": user.get("shortName"),
                        "longname": user.get("longName"),
                    },
                    "hops_away": node.get("hops_away"),
                    "last_heard": node.get("last_heard") or node.get("last_update_ts") or now,
                }


def persist_state(client: mqtt.Client):
    with LOCK:
        cutoff = ts_now() - 3600
        while RX_EVENTS and RX_EVENTS[0]["ts"] < cutoff:
            RX_EVENTS.popleft()
        STATE["rx_1h_count"] = len(RX_EVENTS)
        STATE["policy_decisions"] = dict(POLICY_COUNTER)
        STATE["node_count"] = len(STATE["nodes"])
        snap = {
            "ts": ts_now(),
            **STATE,
            "nodes": list(STATE["nodes"].values())[:200],
            "safety_state": get_safety_state(),
            "rollout_mode": ROLL_OUT_MODE,
            "canary_percent": CANARY_PERCENT,
        }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(_json_dumps(snap))

    health_payload = {
        "ts": ts_now(),
        "agent": "Real Joe",
        "status": "online",
        "engine": "openclaw",
        "fallback_engine": "real-joe-local",
        "rx_1h_count": snap["rx_1h_count"],
        "node_count": snap["node_count"],
        "safety_state": snap["safety_state"],
        "rollout_mode": snap["rollout_mode"],
        "canary_percent": snap["canary_percent"],
    }
    publish_json(client, HEALTH_TOPIC, health_payload)


def snapshot_loop(client: mqtt.Client):
    while not STOP.wait(max(5, SNAPSHOT_SECONDS)):
        try:
            persist_state(client)
        except Exception as exc:
            print(f"snapshot error: {exc}", flush=True)


def init_safety_defaults(client: mqtt.Client):
    current = get_safety_state()
    redis_set_json("safety_state", current, ttl_seconds=REDIS_TTL_SECONDS * 30)
    emit_policy_event(client, "safety_state_initialized", safety_state=current)


def build_client() -> mqtt.Client:
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
    except Exception:
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    if BROKER_USER or BROKER_PASSWORD:
        client.username_pw_set(BROKER_USER or "", BROKER_PASSWORD or "")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


def main():
    global REDIS
    REDIS = redis_connect()

    _hq_ensure_layout()

    client = build_client()

    def _stop(*_):
        STOP.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    init_safety_defaults(client)

    t = threading.Thread(target=snapshot_loop, args=(client,), daemon=True)
    t.start()

    try:
        while not STOP.wait(1):
            pass
    finally:
        try:
            persist_state(client)
        except Exception:
            pass
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
