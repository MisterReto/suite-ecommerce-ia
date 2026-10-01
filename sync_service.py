"""WooCommerce tools without importing Gradio, Gemini, pandas or the AI app."""
import json
import os
import secrets
import sys
import time
import types
from threading import Lock

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from inventory_schema import MASTER_COLUMNS, MASTER_SHEET
from sync_bridge_protocol import STORE_CONTEXT, STORE_KEYS, TOOL_PATHS, verify

runtime = types.ModuleType("app")
runtime.fastapi_app = FastAPI(title="Suite WooCommerce tools")
runtime.SESSIONS = {}


def _service(api, version, session):
    return build(api, version, credentials=Credentials(token=session["access_token"]), cache_discovery=False)


def _prepared(_drive, session):
    return session["root_folder_id"], session["images_folder_id"], session["spreadsheet_id"], None


def _validate(sheets, spreadsheet_id):
    rows = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"'{MASTER_SHEET}'!A1:N1"
    ).execute().get("values", [])
    if not rows or list(rows[0]) != list(MASTER_COLUMNS):
        raise ValueError("Los encabezados de Lista completa no coinciden con el formato de la app.")


runtime._get_drive_service = lambda session: _service("drive", "v3", session)
runtime._get_sheets_service = lambda session: _service("sheets", "v4", session)
runtime._preparar_estructura = _prepared
runtime._validar_inventario_preparado = _validate
sys.modules["app"] = runtime

# Reuse the existing pages and callbacks. Only the runtime is lightweight.
import product_web
import batch_web_v2

app = FastAPI(title="Suite sync service")
_NONCES = {}
_NONCE_LOCK = Lock()


@app.get("/health")
def health():
    return {"ok": True, "role": "sync", "bridge_configured": len(os.getenv("SYNC_SERVICE_SHARED_KEY", "")) >= 32,
            "store_connected": os.getenv("SUITE_DRIVE_ONLY", "true").lower() == "false"}


@app.post("/internal/tools")
async def tools(request: Request):
    if int(request.headers.get("content-length", "0")) > 2_000_000:
        return JSONResponse({"error": "Solicitud demasiado grande."}, status_code=413)
    raw = await request.body()
    if len(raw) > 2_000_000:
        return JSONResponse({"error": "Solicitud demasiado grande."}, status_code=413)
    nonce = request.headers.get("x-suite-nonce", "")
    if not verify(raw, request.headers.get("x-suite-time"), nonce,
                  request.headers.get("x-suite-signature"), os.getenv("SYNC_SERVICE_SHARED_KEY", "")):
        return JSONResponse({"error": "Solicitud no autorizada."}, status_code=401)
    with _NONCE_LOCK:
        now = time.time()
        for old, ts in list(_NONCES.items()):
            if now - ts > 120:
                del _NONCES[old]
        if nonce in _NONCES or len(_NONCES) >= 1000:
            return JSONResponse({"error": "Solicitud repetida o servicio ocupado."}, status_code=409)
        _NONCES[nonce] = now
    try:
        data = json.loads(raw)
        method, path = data["method"], data["path"]
        if method not in {"GET", "POST"} or path not in TOOL_PATHS:
            raise ValueError()
        context = data["context"]
        if not all(isinstance(context.get(k), str) and context[k] for k in (
            "access_token", "spreadsheet_id", "images_folder_id", "root_folder_id"
        )):
            raise ValueError()
        store = {k: v for k, v in context.get("store", {}).items() if k in STORE_KEYS and isinstance(v, str)}
        payload = data.get("body", "")
        query = data.get("query", "")
        if not isinstance(payload, str) or not isinstance(query, str) or "#" in query:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        return JSONResponse({"error": "Solicitud inválida."}, status_code=400)
    # A fresh per-request session cannot overwrite another customer's tokens.
    sid = secrets.token_urlsafe(32)
    runtime.SESSIONS[sid] = {**context, "session_id": sid}
    scope_token = STORE_CONTEXT.set(store)
    try:
        transport = httpx.ASGITransport(app=runtime.fastapi_app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://sync-local") as client:
            result = await client.request(method, path + ("?" + query if query else ""),
                content=payload.encode(), headers={"cookie": f"session_id={sid}", "content-type": "application/json"})
        return Response(result.content, status_code=result.status_code, headers={
            "content-type": result.headers.get("content-type", "application/json"), "cache-control": "no-store",
        })
    finally:
        STORE_CONTEXT.reset(scope_token)
        runtime.SESSIONS.pop(sid, None)
