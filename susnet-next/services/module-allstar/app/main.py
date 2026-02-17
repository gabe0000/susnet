from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import Body, FastAPI, Query
from fastapi.responses import JSONResponse

V1_BASE_URL = os.getenv("V1_BASE_URL", "http://host.docker.internal:8088")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))

app = FastAPI(title="susnet-module-allstar", version="0.1.0")


def _wrap_ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data, "errors": []}


def _wrap_err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "data": None, "errors": [msg]}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        resp = httpx.get(f"{V1_BASE_URL}{path}", params=params, timeout=TIMEOUT)
    except Exception as exc:
        return _wrap_err(str(exc))
    if resp.status_code >= 400:
        return _wrap_err(f"{resp.status_code}: {resp.text[:200]}")
    return _wrap_ok(_safe_json(resp))


def _post(path: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
    try:
        resp = httpx.post(f"{V1_BASE_URL}{path}", json=payload, timeout=timeout or TIMEOUT)
    except Exception as exc:
        return _wrap_err(str(exc))
    if resp.status_code >= 400:
        return _wrap_err(f"{resp.status_code}: {resp.text[:200]}")
    return _wrap_ok(_safe_json(resp))


@app.get("/health")
def health():
    return {"ok": True, "service": "allstar", "v1_base": V1_BASE_URL}


@app.get("/status")
def status():
    return _get("/api/services")


@app.get("/nodes")
def nodes():
    return _get("/api/nodes")


@app.get("/extnodes")
def extnodes(node: str = Query(...), limit: int = Query(20)):
    return _get("/api/allstar/gmrs-extnodes", {"node": node, "limit": limit})


@app.post("/refresh-extnodes")
def refresh_extnodes():
    return _post("/api/allstar/refresh-gmrs-list", {})


@app.get("/inbound/health")
def inbound_health(node: Optional[str] = Query(None)):
    params: Dict[str, Any] = {}
    if node:
        params["node"] = str(node)
    return _get("/api/allstar/inbound-health", params)


@app.post("/inbound/test-window")
def inbound_test_window(payload: Dict[str, Any] = Body(default={})):
    req_timeout = TIMEOUT
    if isinstance(payload, dict):
        try:
            req_timeout = max(TIMEOUT, float(payload.get("duration", 45)) + 10.0)
        except Exception:
            req_timeout = TIMEOUT
    return _post("/api/allstar/inbound-test-window", payload, timeout=req_timeout)


@app.get("/debug/ping")
def debug_ping():
    return {"ok": True}


@app.exception_handler(Exception)
async def unhandled_exception(_, exc: Exception):
    return JSONResponse(status_code=500, content=_wrap_err(str(exc)))
