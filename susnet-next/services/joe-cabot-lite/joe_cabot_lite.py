#!/usr/bin/env python3
import json
import os
import re
import signal
import subprocess
import threading
import time
from collections import Counter, deque
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("BROKER_HOST", "100.124.168.35")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
BROKER_USER = os.getenv("BROKER_USER") or None
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD") or None

QUERY_TOPIC = os.getenv("QUERY_TOPIC", "susnet/agent/query")
REPLY_TOPIC = os.getenv("REPLY_TOPIC", "susnet/agent/reply")
ACK_TOPIC = os.getenv("ACK_TOPIC", "susnet/agent/ack")
PROGRESS_TOPIC = os.getenv("PROGRESS_TOPIC", "susnet/agent/progress")
CONTROL_TOPIC = os.getenv("CONTROL_TOPIC", "susnet/agent/control")
ERROR_TOPIC = os.getenv("ERROR_TOPIC", "susnet/agent/error")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "susnet/agent/dlq")
HEALTH_TOPIC = os.getenv("HEALTH_TOPIC", "susnet/agent/events/health")

STATE_PATH = Path(os.getenv("STATE_PATH", "/data/state/agents/joe-cabot/state.json"))
SNAPSHOT_SECONDS = int(os.getenv("SNAPSHOT_SECONDS", "30"))
RF_MAX_CHUNKS = int(os.getenv("RF_MAX_CHUNKS", "5"))
RF_CHUNK_CHARS = int(os.getenv("RF_CHUNK_CHARS", "110"))
MAX_NODES_DETAIL = int(os.getenv("MAX_NODES_DETAIL", "7"))
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
OLLAMA_CONTAINER = os.getenv("OLLAMA_CONTAINER", "openclaw-ollama")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_URL = (os.getenv("OLLAMA_URL") or "").strip()
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "12"))
OLLAMA_IP_CACHE_SECONDS = int(os.getenv("OLLAMA_IP_CACHE_SECONDS", "120"))
RF_RESPONSE_HEADROOM_CHARS = int(os.getenv("RF_RESPONSE_HEADROOM_CHARS", "30"))
STILL_WORKING_INTERVAL_SECONDS = int(os.getenv("STILL_WORKING_INTERVAL_SECONDS", "10"))

SUB_TOPICS = [
    ("meshbox/agent/events/rx", 0),
    ("meshbox/agent/events/policy", 0),
    ("meshbox/agent/events/health", 0),
    ("meshbox/agent/events/nodes", 0),
    (QUERY_TOPIC, 0),
    (CONTROL_TOPIC, 0),
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
OLLAMA_IP_CACHE = {"ts": 0, "url": None}
INFLIGHT = {}
INFLIGHT_LOCK = threading.Lock()


def ts_now() -> int:
    return int(time.time())


def normalize_identity(identity):
    if not isinstance(identity, dict):
        return {"node_id": None, "shortname": None, "longname": None}
    return {
        "node_id": identity.get("node_id"),
        "shortname": identity.get("shortname"),
        "longname": identity.get("longname"),
    }


def node_name(identity: dict) -> str:
    if identity.get("longname"):
        return identity["longname"]
    if identity.get("shortname"):
        return identity["shortname"]
    if identity.get("node_id"):
        return f"Unknown Node ({identity['node_id']})"
    return "Unknown Node"


def _coerce_positive_int(value, default):
    try:
        n = int(value)
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
            # Keep words from spilling across chunk boundaries by clipping oversized tokens in-place.
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


def persist_state(client):
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
        }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(snap, separators=(",", ":"), ensure_ascii=True))

    client.publish(
        HEALTH_TOPIC,
        json.dumps(
            {
                "ts": ts_now(),
                "agent": "Joe Cabot",
                "status": "online",
                "rx_1h_count": snap["rx_1h_count"],
                "node_count": snap["node_count"],
                "topic_source": "meshbox/agent/events/#",
            },
            separators=(",", ":"),
        ),
        qos=0,
        retain=False,
    )


def activity_summary():
    with LOCK:
        recent = list(RX_EVENTS)
    if not recent:
        return "Activity summary: no recent RF traffic in the last hour."
    senders = Counter(x.get("sender_name", "Unknown Node") for x in recent)
    top = ", ".join(f"{name}({count})" for name, count in senders.most_common(5))
    return f"Activity summary (1h): {len(recent)} messages, {len(senders)} active nodes. Top talkers: {top}."


def traffic_summary():
    now = ts_now()
    with LOCK:
        recent = [x for x in RX_EVENTS if x["ts"] >= now - 300]
        recent_1h = [x for x in RX_EVENTS if x["ts"] >= now - 3600]
    by_ch_5m = Counter(x.get("channel_index", 0) for x in recent)
    by_ch_1h = Counter(x.get("channel_index", 0) for x in recent_1h)

    def fmt(counter):
        return "none" if not counter else ", ".join(f"ch{k}:{v}" for k, v in sorted(counter.items()))

    return f"Traffic load: 5m={len(recent)} msgs ({fmt(by_ch_5m)}); 1h={len(recent_1h)} msgs ({fmt(by_ch_1h)})."


def nodes_in_range():
    with LOCK:
        nodes = list(STATE["nodes"].values())
    if not nodes:
        return "Nodes in range: none recorded yet."
    if len(nodes) > MAX_NODES_DETAIL:
        return (
            f"There are {len(nodes)} nodes online over RF. "
            "I am in lightweight mode, so ask for a narrower slice like top recently heard nodes."
        )
    nodes.sort(key=lambda n: n.get("last_heard", 0), reverse=True)
    names = [node_name(n.get("identity", {})) for n in nodes[:MAX_NODES_DETAIL]]
    return f"Nodes in range ({len(nodes)}): " + "; ".join(names)


def _ollama_base_url():
    if OLLAMA_URL:
        return OLLAMA_URL.rstrip("/")

    now = ts_now()
    cached_url = OLLAMA_IP_CACHE.get("url")
    cached_ts = int(OLLAMA_IP_CACHE.get("ts", 0))
    if cached_url and (now - cached_ts) <= OLLAMA_IP_CACHE_SECONDS:
        return cached_url

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


def _ollama_generate(prompt: str, max_output_chars=None) -> str | None:
    if not OLLAMA_ENABLED:
        return None

    base = _ollama_base_url()
    if not base:
        return None

    with LOCK:
        node_count = len(STATE["nodes"])
        rx_1h = STATE.get("rx_1h_count", 0)

    system = (
        "You are Joe Cabot, a lightweight local mesh assistant for Meshtastic operations. "
        "Keep answers concise, practical, and safe. If a request is too broad for RF constraints, "
        "refuse and suggest one narrower question. Avoid claiming actions you cannot perform."
    )

    target_max_chars = _coerce_positive_int(max_output_chars, RF_MAX_CHUNKS * RF_CHUNK_CHARS - RF_RESPONSE_HEADROOM_CHARS)
    if target_max_chars < 80:
        target_max_chars = 80

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "keep_alive": "30m",
        "system": system,
        "prompt": (
            f"Context: node_count={node_count}, rx_1h={rx_1h}.\n"
            f"Policy: responses should fit lightweight RF use; keep it brief and <= {target_max_chars} chars.\n"
            "Formatting: plain text only, complete words, no markdown.\n"
            f"User request: {prompt}"
        ),
        "options": {
            "temperature": 0.0,
            "num_predict": 96,
            "num_ctx": 1024,
        },
    }

    body = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{base}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError):
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    text = str(parsed.get("response", "")).strip()
    return text or None


def _is_broad_request(t: str) -> bool:
    broad_markers = (
        "list all",
        "everything",
        "full list",
        "detailed list",
        "every node",
        "all nodes",
        "all traffic",
        "all messages",
        "dump",
        "entire",
    )
    return any(marker in t for marker in broad_markers)


def _extract_user_request(text: str) -> str:
    raw = str(text or "")
    marker = "RF output constraints:"
    if marker in raw:
        raw = raw.split(marker, 1)[0]
    return _normalize_text(raw)


def _safe_arithmetic_reply(text: str) -> str | None:
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


def _local_conversation_reply(text: str) -> str:
    t = (text or "").lower().strip()
    with LOCK:
        node_count = len(STATE["nodes"])
        rx_1h = STATE.get("rx_1h_count", 0)

    if re.search(r"\b(hello|hi|hey|yo)\b", t):
        return f"Hi. I am online in lightweight mode. Current mesh view: {node_count} known nodes, {rx_1h} messages in the last hour."
    if "who are you" in t or "what are you" in t:
        return "I am the local control-plane assistant. Mr. Pink handles edge RF routing; I provide lightweight summaries and guidance."
    if "what can you do" in t or "help" in t:
        return "I can provide activity summaries, traffic load snapshots, nodes-in-range summaries, and short operational guidance for mesh tasks."
    if "online" in t or "alive" in t or "status" in t:
        return f"I am online. Mesh snapshot: {node_count} known nodes and {rx_1h} messages in the last hour."
    if "thank" in t:
        return "Copy that. Send another short query when ready."
    return (
        "I can help with concise mesh operations chat. Try: 'activity summary', 'traffic load', "
        "or 'how many nodes are in range right now?'."
    )




def answer_query(text: str, max_output_chars=None) -> str:
    user_text = _extract_user_request(text)
    t = user_text.lower().strip()

    arithmetic = _safe_arithmetic_reply(user_text)
    if arithmetic is not None:
        return arithmetic

    if _is_broad_request(t):
        return (
            "I am running in lightweight local mode and cannot process that broad request. "
            "Please ask a narrower question, for example: how many RF nodes in the last 15 minutes?"
        )

    if re.search(r"\b(traffic|load|busy|volume)\b", t):
        return traffic_summary()

    if re.search(r"\b(nodes?|in\s+range|rf\s+range|seen|online|around)\b", t):
        return nodes_in_range()

    if re.search(r"\b(activity|summary|summarize|recap)\b", t):
        return activity_summary()

    if re.search(r"\b(restart|reboot|shutdown|install|delete|wipe|format|rm\s+-rf|apt\s+|docker\s+)\b", t):
        return (
            "I can help reason about that, but I am in safe lightweight mode and will not run broad system mutations "
            "from RF chat. Ask for a specific status check or summary instead."
        )

    llm_reply = _ollama_generate(user_text, max_output_chars=max_output_chars)
    if llm_reply:
        return llm_reply

    return _local_conversation_reply(user_text)



def publish_json(client, topic, payload):
    client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=0, retain=False)


def make_envelope(parsed, request_id):
    sender_obj = parsed.get("sender") if isinstance(parsed.get("sender"), dict) else {"node_id": parsed.get("sender")}
    sender_obj = {
        "node_id": sender_obj.get("node_id"),
        "shortname": sender_obj.get("shortname"),
        "longname": sender_obj.get("longname"),
    }
    return {
        "request_id": request_id,
        "session_id": str(parsed.get("session_id") or f"sess-{request_id}"),
        "sender": sender_obj,
        "channel_index": int(parsed.get("channel_index") or 0),
        "origin": str(parsed.get("origin") or "meshtastic"),
        "created_ts": int(parsed.get("created_ts") or ts_now()),
        "expires_ts": int(parsed.get("expires_ts") or (ts_now() + 180)),
        "trace": parsed.get("trace") or {"control_host": "susnet", "version": "joe-cabot-lite-v2"},
    }


def emit_ack(client, env):
    payload = {"ts": ts_now(), **env, "status": "accepted"}
    publish_json(client, ACK_TOPIC, payload)


def emit_progress(client, env, stage, **extra):
    payload = {"ts": ts_now(), **env, "stage": stage}
    payload.update(extra)
    publish_json(client, PROGRESS_TOPIC, payload)


def emit_error(client, env, error, **extra):
    payload = {"ts": ts_now(), **env, "error": str(error)}
    payload.update(extra)
    publish_json(client, ERROR_TOPIC, payload)


def emit_dlq(client, reason, raw_payload, topic):
    payload = {"ts": ts_now(), "reason": reason, "topic": topic, "payload": raw_payload}
    publish_json(client, DLQ_TOPIC, payload)


def _still_working_loop(client, env, done_event):
    while not done_event.wait(STILL_WORKING_INTERVAL_SECONDS):
        emit_progress(client, env, "still_working")


def process_query_request(client, env, parsed, cancel_event, done_event):
    started = time.time()
    emit_progress(client, env, "started")

    worker = threading.Thread(target=_still_working_loop, args=(client, env, done_event), daemon=True)
    worker.start()

    try:
        if cancel_event.is_set():
            emit_progress(client, env, "canceled")
            return

        text = parsed.get("text") if isinstance(parsed, dict) else ""
        max_output_chars = parsed.get("max_output_chars") if isinstance(parsed, dict) else None
        rf_chunk_chars = parsed.get("rf_chunk_chars") if isinstance(parsed, dict) else None
        rf_max_chunks = parsed.get("rf_max_chunks") if isinstance(parsed, dict) else None

        reply = answer_query(text, max_output_chars=max_output_chars)

        if cancel_event.is_set():
            emit_progress(client, env, "canceled")
            return

        chunks = bounded_chunks(
            reply,
            max_chunks=rf_max_chunks,
            chunk_chars=rf_chunk_chars,
            max_output_chars=max_output_chars,
        )
        for i, chunk in enumerate(chunks, start=1):
            payload = {
                "ts": ts_now(),
                **env,
                "text": chunk,
                "chunk_index": i,
                "chunk_count": len(chunks),
            }
            publish_json(client, REPLY_TOPIC, payload)

        elapsed_ms = int((time.time() - started) * 1000)
        emit_progress(client, env, "completed", total_ms=elapsed_ms, process_ms=elapsed_ms, queue_ms=0)
    except Exception as exc:
        emit_error(client, env, exc)
    finally:
        done_event.set()
        with INFLIGHT_LOCK:
            INFLIGHT.pop(env["request_id"], None)


def on_connect(client, userdata, flags, rc):
    print(f"MQTT connected rc={rc} to {BROKER_HOST}:{BROKER_PORT}", flush=True)
    for topic, qos in SUB_TOPICS:
        client.subscribe(topic, qos=qos)
        print(f"subscribed {topic}", flush=True)


def on_message(client, userdata, msg):
    topic = msg.topic
    raw = msg.payload.decode("utf-8", errors="replace")

    if topic == CONTROL_TOPIC:
        try:
            parsed = json.loads(raw)
        except Exception:
            emit_dlq(client, "malformed_control", raw, topic)
            return

        request_id = str(parsed.get("request_id") or "").strip()
        if not request_id:
            emit_dlq(client, "control_missing_request_id", parsed, topic)
            return

        with INFLIGHT_LOCK:
            inflight = INFLIGHT.get(request_id)
        env = (inflight or {}).get("env") or make_envelope(parsed if isinstance(parsed, dict) else {}, request_id)
        if not inflight:
            emit_error(client, env, "request_not_found", stage="cancel")
            return

        inflight["cancel_event"].set()
        inflight["done_event"].set()
        with INFLIGHT_LOCK:
            INFLIGHT.pop(request_id, None)
        emit_progress(client, env, "cancel_requested")
        emit_progress(client, env, "canceled")
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

        cancel_event = threading.Event()
        done_event = threading.Event()
        with INFLIGHT_LOCK:
            INFLIGHT[request_id] = {
                "cancel_event": cancel_event,
                "done_event": done_event,
                "started_ts": ts_now(),
                "env": env,
            }

        emit_ack(client, env)
        emit_progress(client, env, "queued")

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
        sender_identity = normalize_identity(((payload.get("sender") or {}).get("identity")))
        event = {
            "ts": int(payload.get("ts") or ts_now()),
            "channel_index": int(payload.get("channel_index") or 0),
            "sender_name": node_name(sender_identity),
            "sender_identity": sender_identity,
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
                POLICY_COUNTER[decision] += 1
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
                identity = normalize_identity(node.get("user") and {
                    "node_id": node.get("node_id"),
                    "shortname": (node.get("user") or {}).get("shortName"),
                    "longname": (node.get("user") or {}).get("longName"),
                } or {
                    "node_id": node.get("node_id"),
                    "shortname": None,
                    "longname": None,
                })
                STATE["nodes"][identity.get("node_id") or f"unknown-{now}"] = {
                    "identity": identity,
                    "hops_away": node.get("hops_away"),
                    "last_heard": node.get("last_heard") or node.get("last_update_ts") or now,
                }


def snapshot_loop(client):
    while not STOP.wait(SNAPSHOT_SECONDS):
        try:
            persist_state(client)
        except Exception as exc:
            print(f"snapshot error: {exc}", flush=True)


def main():
    client = mqtt.Client()
    if BROKER_USER or BROKER_PASSWORD:
        client.username_pw_set(BROKER_USER or "", BROKER_PASSWORD or "")
    client.on_connect = on_connect
    client.on_message = on_message

    def _stop(*_):
        STOP.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

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
