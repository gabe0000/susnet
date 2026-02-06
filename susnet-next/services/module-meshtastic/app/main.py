from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse

V1_BASE_URL = os.getenv("V1_BASE_URL", "http://host.docker.internal:8088")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))

app = FastAPI(title="susnet-module-meshtastic", version="0.1.0")


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


def _post(path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        resp = httpx.post(f"{V1_BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    except Exception as exc:
        return _wrap_err(str(exc))
    if resp.status_code >= 400:
        return _wrap_err(f"{resp.status_code}: {resp.text[:200]}")
    return _wrap_ok(_safe_json(resp))


@app.get("/health")
def health():
    return {"ok": True, "service": "meshtastic", "v1_base": V1_BASE_URL}


@app.get("/messages")
def messages():
    return _get("/api/meshtastic/messages")


@app.get("/telemetry")
def telemetry():
    return _get("/api/meshtastic/telemetry")


@app.post("/send")
def send(payload: Dict[str, Any] = Body(default={})):  # passthrough to v1
    return _post("/api/meshtastic/send", payload)


@app.exception_handler(Exception)
async def unhandled_exception(_, exc: Exception):
    return JSONResponse(status_code=500, content=_wrap_err(str(exc)))
