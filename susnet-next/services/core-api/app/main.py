from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Body, Query
from fastapi.responses import JSONResponse

ALLSTAR_API_URL = os.getenv("ALLSTAR_API_URL", "http://module-allstar:8080")
GMRS_API_URL = os.getenv("GMRS_API_URL", "http://module-gmrshub:8080")
APRS_API_URL = os.getenv("APRS_API_URL", "http://module-aprs:8080")
MESH_API_URL = os.getenv("MESH_API_URL", "http://module-meshtastic:8080")
V1_BASE_URL = os.getenv("V1_BASE_URL", "http://host.docker.internal:8088")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))
MESH_CACHE_TTL_SECONDS = float(os.getenv("MESH_CACHE_TTL_SECONDS", "5.0"))
MESH_CACHE_TTL_OVERRIDES = {
    "/health": float(os.getenv("MESH_CACHE_TTL_HEALTH_SECONDS", "5.0")),
    "/nodes": float(os.getenv("MESH_CACHE_TTL_NODES_SECONDS", "12.0")),
    "/messages": float(os.getenv("MESH_CACHE_TTL_MESSAGES_SECONDS", "6.0")),
    "/telemetry": float(os.getenv("MESH_CACHE_TTL_TELEMETRY_SECONDS", "6.0")),
    "/mqtt/status": float(os.getenv("MESH_CACHE_TTL_MQTT_STATUS_SECONDS", "6.0")),
    "/mqtt/messages": float(os.getenv("MESH_CACHE_TTL_MQTT_MESSAGES_SECONDS", "6.0")),
}
_MESH_CACHE: Dict[str, Dict[str, Any]] = {}
_MESH_CACHE_LOCK = threading.Lock()
_MESH_INFLIGHT: Dict[str, threading.Event] = {}
_MESH_INFLIGHT_LOCK = threading.Lock()

# Reuse pooled connections instead of building a new socket for each poll.
_HTTP_CLIENT = httpx.Client()

app = FastAPI(title="susnet-core-api", version="0.2.0")


def _wrap_err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "errors": [msg]}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _mesh_cache_key(path: str, params: Optional[Dict[str, Any]]) -> str:
    if not params:
        return path
    pairs = tuple(sorted((str(k), str(v)) for k, v in params.items()))
    return f"{path}?{pairs}"


def _mesh_cache_get(path: str, params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    ttl = max(0.0, float(MESH_CACHE_TTL_OVERRIDES.get(path, MESH_CACHE_TTL_SECONDS)))
    if ttl <= 0:
        return None
    key = _mesh_cache_key(path, params)
    now = time.monotonic()
    with _MESH_CACHE_LOCK:
        entry = _MESH_CACHE.get(key)
        if not entry:
            return None
        if float(entry.get("expires_at", 0.0)) <= now:
            _MESH_CACHE.pop(key, None)
            return None
        return entry.get("value")


def _mesh_cache_put(path: str, params: Optional[Dict[str, Any]], value: Dict[str, Any]) -> None:
    ttl = max(0.0, float(MESH_CACHE_TTL_OVERRIDES.get(path, MESH_CACHE_TTL_SECONDS)))
    if ttl <= 0:
        return
    key = _mesh_cache_key(path, params)
    with _MESH_CACHE_LOCK:
        _MESH_CACHE[key] = {"expires_at": time.monotonic() + ttl, "value": value}


def _mesh_cache_clear() -> None:
    with _MESH_CACHE_LOCK:
        _MESH_CACHE.clear()


def _http_get(
    url: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        resp = _HTTP_CLIENT.get(f"{url}{path}", params=params, timeout=timeout or TIMEOUT)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "data": None}
    if resp.status_code >= 400:
        return {"ok": False, "errors": [f"{resp.status_code}: {resp.text[:200]}"]}
    return _safe_json(resp)


def _mesh_get_singleflight(
    path: str,
    params: Optional[Dict[str, Any]],
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    key = _mesh_cache_key(path, params)
    cached = _mesh_cache_get(path, params)
    if isinstance(cached, dict):
        return cached

    owner = False
    with _MESH_INFLIGHT_LOCK:
        event = _MESH_INFLIGHT.get(key)
        if event is None:
            event = threading.Event()
            _MESH_INFLIGHT[key] = event
            owner = True

    if owner:
        try:
            payload = _http_get(MESH_API_URL, path, params=params, timeout=timeout)
            if isinstance(payload, dict) and payload.get("ok"):
                _mesh_cache_put(path, params, payload)
            return payload
        finally:
            with _MESH_INFLIGHT_LOCK:
                waiter = _MESH_INFLIGHT.pop(key, None)
                if waiter is not None:
                    waiter.set()

    wait_timeout = max(0.2, float(timeout or TIMEOUT))
    event.wait(wait_timeout)
    cached = _mesh_cache_get(path, params)
    if isinstance(cached, dict):
        return cached
    return _http_get(MESH_API_URL, path, params=params, timeout=timeout)


def _get(
    url: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    use_mesh_cache = bool(url == MESH_API_URL and path in MESH_CACHE_TTL_OVERRIDES)
    if use_mesh_cache:
        return _mesh_get_singleflight(path, params=params, timeout=timeout)
    return _http_get(url, path, params=params, timeout=timeout)


def _post(
    url: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        resp = _HTTP_CLIENT.post(f"{url}{path}", json=payload, timeout=timeout or TIMEOUT)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "data": None}
    if resp.status_code >= 400:
        return {"ok": False, "errors": [f"{resp.status_code}: {resp.text[:200]}"]}

    payload_out = _safe_json(resp)
    if url == MESH_API_URL:
        _mesh_cache_clear()
    return payload_out


def _unwrap_or_error(module_resp: Dict[str, Any]) -> Dict[str, Any]:
    if not module_resp.get("ok"):
        return {"ok": False, "errors": module_resp.get("errors", ["module error"])}
    return {"ok": True, **(module_resp.get("data") or {})}


def _redact_nodes(payload: Dict[str, Any]) -> Dict[str, Any]:
    nodes = payload.get("nodes", [])
    if isinstance(nodes, list):
        for n in nodes:
            if isinstance(n, dict):
                n.pop("password", None)
    return payload


@app.get("/api/health")
def health():
    allstar = _get(ALLSTAR_API_URL, "/health")
    gmrshub = _get(GMRS_API_URL, "/health")
    aprs = _get(APRS_API_URL, "/health")
    mesh = _get(MESH_API_URL, "/health")
    return {
        "ok": True,
        "services": {
            "allstar": allstar.get("ok", False),
            "gmrshub": gmrshub.get("ok", False),
            "aprs": aprs.get("ok", False),
            "meshtastic": mesh.get("ok", False),
        },
        "version": app.version,
    }


@app.get("/api/services")
def services():
    return _get(V1_BASE_URL, "/api/services")


@app.get("/api/tickets")
def tickets():
    return _get(V1_BASE_URL, "/api/tickets")


# AllStar
@app.get("/api/allstar/nodes")
def allstar_nodes():
    resp = _get(ALLSTAR_API_URL, "/nodes")
    data = _unwrap_or_error(resp)
    if data.get("ok"):
        return _redact_nodes(data)
    return data


@app.get("/api/allstar/extnodes")
def allstar_extnodes(node: str = Query(...), limit: int = Query(20)):
    resp = _get(ALLSTAR_API_URL, "/extnodes", {"node": node, "limit": limit})
    return _unwrap_or_error(resp)


@app.post("/api/allstar/refresh-extnodes")
def allstar_refresh_extnodes():
    resp = _post(ALLSTAR_API_URL, "/refresh-extnodes", {})
    return _unwrap_or_error(resp)


@app.get("/api/allstar/inbound/health")
def allstar_inbound_health(node: Optional[str] = Query(None)):
    params: Dict[str, Any] = {}
    if node:
        params["node"] = str(node)
    resp = _get(ALLSTAR_API_URL, "/inbound/health", params)
    return _unwrap_or_error(resp)


@app.post("/api/allstar/inbound/test-window")
def allstar_inbound_test_window(payload: Dict[str, Any] = Body(default={})):
    req_timeout = TIMEOUT
    if isinstance(payload, dict):
        try:
            req_timeout = max(TIMEOUT, float(payload.get("duration", 45)) + 15.0)
        except Exception:
            req_timeout = TIMEOUT
    resp = _post(ALLSTAR_API_URL, "/inbound/test-window", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


# GMRSHub
@app.get("/api/gmrshub/nodes")
def gmrshub_nodes():
    resp = _get(GMRS_API_URL, "/nodes")
    data = _unwrap_or_error(resp)
    if data.get("ok"):
        return _redact_nodes(data)
    return data


@app.get("/api/gmrshub/extnodes")
def gmrshub_extnodes(node: str = Query(...), limit: int = Query(20)):
    resp = _get(GMRS_API_URL, "/extnodes", {"node": node, "limit": limit})
    return _unwrap_or_error(resp)


@app.post("/api/gmrshub/refresh-extnodes")
def gmrshub_refresh_extnodes():
    resp = _post(GMRS_API_URL, "/refresh-extnodes", {})
    return _unwrap_or_error(resp)


@app.get("/api/gmrshub/inbound/health")
def gmrshub_inbound_health(node: Optional[str] = Query(None)):
    params: Dict[str, Any] = {}
    if node:
        params["node"] = str(node)
    resp = _get(GMRS_API_URL, "/inbound/health", params)
    return _unwrap_or_error(resp)


@app.post("/api/gmrshub/inbound/test-window")
def gmrshub_inbound_test_window(payload: Dict[str, Any] = Body(default={})):
    req_timeout = TIMEOUT
    if isinstance(payload, dict):
        try:
            req_timeout = max(TIMEOUT, float(payload.get("duration", 45)) + 15.0)
        except Exception:
            req_timeout = TIMEOUT
    resp = _post(GMRS_API_URL, "/inbound/test-window", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


# APRS
@app.get("/api/aprs/config")
def aprs_config():
    resp = _get(APRS_API_URL, "/config")
    return _unwrap_or_error(resp)


@app.get("/api/aprs/messages")
def aprs_messages():
    resp = _get(APRS_API_URL, "/messages")
    return _unwrap_or_error(resp)


@app.post("/api/aprs/send")
def aprs_send(payload: Dict[str, Any] = Body(default={})):  # passthrough
    resp = _post(APRS_API_URL, "/send", payload)
    return _unwrap_or_error(resp)


# Meshtastic
@app.get("/api/meshtastic/messages")
def mesh_messages():
    resp = _get(MESH_API_URL, "/messages")
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/telemetry")
def mesh_telemetry():
    resp = _get(MESH_API_URL, "/telemetry")
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/send")
def mesh_send(payload: Dict[str, Any] = Body(default={})):  # passthrough
    resp = _post(MESH_API_URL, "/send", payload)
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/commands")
def mesh_commands():
    resp = _get(MESH_API_URL, "/commands")
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/commands/{command_name}")
def mesh_command(command_name: str, payload: Dict[str, Any] = Body(default={})):
    # Meshtastic CLI-like commands can be long-running (e.g. traceroute/telemetry).
    req_timeout = None
    try:
        if isinstance(payload, dict) and "timeout" in payload and payload["timeout"] is not None:
            req_timeout = max(TIMEOUT, float(payload["timeout"]) + 10.0)
    except Exception:
        req_timeout = None
    resp = _post(MESH_API_URL, f"/commands/{command_name}", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/info")
def mesh_info():
    resp = _get(MESH_API_URL, "/info")
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/nodes")
def mesh_nodes(limit: int = Query(500, ge=1, le=2000)):
    resp = _get(MESH_API_URL, "/nodes", {"limit": limit})
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/channels")
def mesh_channels():
    resp = _get(MESH_API_URL, "/channels")
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/sendtext")
def mesh_sendtext(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/sendtext", payload)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/request-telemetry")
def mesh_request_telemetry(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/request-telemetry", payload)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/request-position")
def mesh_request_position(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/request-position", payload)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/traceroute")
def mesh_traceroute(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/traceroute", payload)
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/config/field")
def mesh_config_field_get(
    field: str = Query(...),
    timeout: float = Query(25, ge=1, le=120),
):
    # Meshtastic config reads often shell out to the CLI behind the module (serial connect + RPC),
    # so they need a longer gateway timeout than the global default.
    resp = _get(MESH_API_URL, "/config/field", {"field": field}, timeout=max(TIMEOUT, timeout))
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/config/field")
def mesh_config_field_set(payload: Dict[str, Any] = Body(default={})):
    req_timeout = None
    try:
        if isinstance(payload, dict) and "timeout" in payload and payload["timeout"] is not None:
            req_timeout = max(TIMEOUT, float(payload["timeout"]) + 10.0)
    except Exception:
        req_timeout = None
    resp = _post(MESH_API_URL, "/config/field", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/channel/set")
def mesh_channel_set(payload: Dict[str, Any] = Body(default={})):
    req_timeout = None
    try:
        if isinstance(payload, dict) and "timeout" in payload and payload["timeout"] is not None:
            req_timeout = max(TIMEOUT, float(payload["timeout"]) + 10.0)
    except Exception:
        req_timeout = None
    resp = _post(MESH_API_URL, "/channel/set", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/channel/add")
def mesh_channel_add(payload: Dict[str, Any] = Body(default={})):
    req_timeout = None
    try:
        if isinstance(payload, dict) and "timeout" in payload and payload["timeout"] is not None:
            req_timeout = max(TIMEOUT, float(payload["timeout"]) + 10.0)
    except Exception:
        req_timeout = None
    resp = _post(MESH_API_URL, "/channel/add", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/channel/delete")
def mesh_channel_delete(payload: Dict[str, Any] = Body(default={})):
    req_timeout = None
    try:
        if isinstance(payload, dict) and "timeout" in payload and payload["timeout"] is not None:
            req_timeout = max(TIMEOUT, float(payload["timeout"]) + 10.0)
    except Exception:
        req_timeout = None
    resp = _post(MESH_API_URL, "/channel/delete", payload, timeout=req_timeout)
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/mqtt/status")
def mesh_mqtt_status():
    resp = _get(MESH_API_URL, "/mqtt/status")
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/mqtt/config")
def mesh_mqtt_config_get():
    resp = _get(MESH_API_URL, "/mqtt/config")
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/config")
def mesh_mqtt_config_set(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/mqtt/config", payload)
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/mqtt/topics")
def mesh_mqtt_topics():
    resp = _get(MESH_API_URL, "/mqtt/topics")
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/connect")
def mesh_mqtt_connect():
    resp = _post(MESH_API_URL, "/mqtt/connect", {})
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/disconnect")
def mesh_mqtt_disconnect():
    resp = _post(MESH_API_URL, "/mqtt/disconnect", {})
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/publish-json")
def mesh_mqtt_publish_json(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/mqtt/publish-json", payload)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/publish-protobuf")
def mesh_mqtt_publish_protobuf(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/mqtt/publish-protobuf", payload)
    return _unwrap_or_error(resp)


@app.get("/api/meshtastic/mqtt/messages")
def mesh_mqtt_messages(limit: int = Query(100, ge=1, le=500)):
    resp = _get(MESH_API_URL, "/mqtt/messages", {"limit": limit})
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/subscribe")
def mesh_mqtt_subscribe(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/mqtt/subscribe", payload)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/unsubscribe")
def mesh_mqtt_unsubscribe(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/mqtt/unsubscribe", payload)
    return _unwrap_or_error(resp)


@app.post("/api/meshtastic/mqtt/downlink/sendtext")
def mesh_mqtt_downlink_sendtext(payload: Dict[str, Any] = Body(default={})):
    resp = _post(MESH_API_URL, "/mqtt/downlink/sendtext", payload)
    return _unwrap_or_error(resp)


@app.exception_handler(Exception)
async def unhandled_exception(_, exc: Exception):
    return JSONResponse(status_code=500, content=_wrap_err(str(exc)))


@app.on_event("shutdown")
def _close_http_client():
    try:
        _HTTP_CLIENT.close()
    except Exception:
        pass
