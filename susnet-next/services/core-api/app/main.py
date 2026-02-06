from __future__ import annotations

import os
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

app = FastAPI(title="susnet-core-api", version="0.2.0")


def _wrap_err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "errors": [msg]}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _get(url: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        resp = httpx.get(f"{url}{path}", params=params, timeout=TIMEOUT)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "data": None}
    if resp.status_code >= 400:
        return {"ok": False, "errors": [f"{resp.status_code}: {resp.text[:200]}"]}
    return _safe_json(resp)


def _post(url: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        resp = httpx.post(f"{url}{path}", json=payload, timeout=TIMEOUT)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "data": None}
    if resp.status_code >= 400:
        return {"ok": False, "errors": [f"{resp.status_code}: {resp.text[:200]}"]}
    return _safe_json(resp)


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


@app.exception_handler(Exception)
async def unhandled_exception(_, exc: Exception):
    return JSONResponse(status_code=500, content=_wrap_err(str(exc)))
