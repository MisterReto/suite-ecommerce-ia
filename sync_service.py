"""WooCommerce tools without importing Gradio, Gemini, pandas or the AI app."""
import json
import os
import secrets
import sys
import time
import types
import html
from urllib.parse import urlencode, urlparse
from threading import Lock

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from inventory_schema import MASTER_COLUMNS, MASTER_SHEET
from sync_bridge_protocol import STORE_CONTEXT, STORE_KEYS, TOOL_PATHS, verify, signature

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
import inventory_hub

app = FastAPI(title="Suite sync service")
_NONCES = {}
_NONCE_LOCK = Lock()

app.mount("/suite-static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="suite-static")


def main_url():
    return os.getenv("MAIN_SERVICE_URL", "https://suite-ecommerce-ia.onrender.com").rstrip("/")


@app.get("/session/start")
async def start_session(ticket: str):
    base = main_url()
    if urlparse(base).scheme != "https":
        return JSONResponse({"error": "Falta configurar el servicio principal."}, status_code=503)
    body = json.dumps({"ticket": ticket}, separators=(",", ":")).encode()
    ts, nonce = str(int(time.time())), secrets.token_urlsafe(24)
    headers = {"x-suite-time": ts, "x-suite-nonce": nonce,
        "x-suite-signature": signature(body, ts, nonce, os.getenv("SYNC_SERVICE_SHARED_KEY", ""))}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            result = await client.post(base + "/sync-handoff/redeem", content=body, headers=headers)
        if result.status_code != 200:
            return Response(result.content, status_code=result.status_code, media_type="application/json")
        data = result.json()
        context, path = data["context"], data["path"]
        if path not in TOOL_PATHS or not context.get("access_token"):
            raise ValueError()
        now = time.time()
        for old, session in list(runtime.SESSIONS.items()):
            if session.get("expires_at", now + 1) < now:
                runtime.SESSIONS.pop(old, None)
        if len(runtime.SESSIONS) >= 500:
            return JSONResponse({"error": "Servicio ocupado."}, status_code=503)
        sid = secrets.token_urlsafe(32)
        runtime.SESSIONS[sid] = {**context, "session_id": sid, "expires_at": now + 600}
        query = data.get("query", "")
        response = RedirectResponse(path + ("?" + query if query else ""), status_code=303,
            headers={"cache-control": "no-store", "referrer-policy": "no-referrer"})
        response.set_cookie("sync_session", sid, max_age=600, secure=True, httponly=True, samesite="lax")
        return response
    except Exception:
        return JSONResponse({"error": "No pude abrir la sesión. Vuelve a la Suite y conecta Drive."}, status_code=502)


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


@app.api_route("/{tool_path:path}", methods=["GET", "POST"])
async def direct_tool(request: Request, tool_path: str):
    path = "/" + tool_path.rstrip("/")
    if path == "/":
        return RedirectResponse(main_url(), status_code=303)
    if path not in TOOL_PATHS:
        return JSONResponse({"error": "Herramienta no disponible."}, status_code=404)
    sid = request.cookies.get("sync_session")
    session = runtime.SESSIONS.get(sid)
    if not session or session.get("expires_at", 0) < time.time():
        runtime.SESSIONS.pop(sid, None)
        if request.method != "GET":
            return JSONResponse({"error": "Sesión caducada. Vuelve a abrir la herramienta desde Suite e-commerce."}, status_code=401)
        return RedirectResponse(main_url() + "/sync-launch?" + urlencode({"path": path, "query": request.url.query}), status_code=303)
    # Browser POSTs must originate on this worker, never from another website.
    if request.method == "POST":
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"error": "Origen no autorizado."}, status_code=403)
    raw = await request.body()
    if len(raw) > 1_000_000:
        return JSONResponse({"error": "Solicitud demasiado grande."}, status_code=413)
    token = STORE_CONTEXT.set({k: v for k, v in session.get("store", {}).items() if k in STORE_KEYS})
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.fastapi_app, raise_app_exceptions=False),
            base_url="http://sync-local") as client:
            result = await client.request(request.method, path + ("?" + request.url.query if request.url.query else ""),
                content=raw, headers={"cookie": f"session_id={sid}",
                    "content-type": request.headers.get("content-type", "application/json")})
        content = result.content
        content_type = result.headers.get("content-type", "application/json")
        if "text/html" in content_type:
            text = content.decode("utf-8")
            import re
            text = re.sub(r"<title>.*?</title>", "<title>Suite e-commerce</title>", text, flags=re.S)
            text = text.replace("</head>", "<link rel='icon' href='/suite-static/rincon-logo.png'></head>")
            text = text.replace("href='/'", f"href='{html.escape(main_url())}'").replace('href="/"', f'href="{html.escape(main_url())}"')
            badge = "<div style='padding:10px 16px;background:#e8f5ee;border-radius:12px;font:14px system-ui'>Suite e-commerce · Ejecutando en el segundo servicio: <b>sincronización WooCommerce</b></div>"
            text = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + badge, text, count=1)
            content = text.encode("utf-8")
        return Response(content, status_code=result.status_code, headers={"content-type": content_type,
            "cache-control": "no-store", "x-suite-executor": "sync-service"})
    finally:
        STORE_CONTEXT.reset(token)
