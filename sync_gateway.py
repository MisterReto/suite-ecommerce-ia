"""Keep existing tool URLs, execute them on the second Render service."""
import asyncio
import json
import os
import secrets
import time
from urllib.parse import urlparse, urlencode

import httpx
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from sync_bridge_protocol import STORE_KEYS, TOOL_PATHS, signature, verify

_HANDOFFS = {}


def redirect_tool(request):
    if request.method != "GET":
        return JSONResponse({"error": "Esta herramienta se ejecuta únicamente en el segundo servicio. Ábrela desde la Suite."}, status_code=409)
    target = os.getenv("SYNC_SERVICE_URL", "").rstrip("/") + request.url.path
    if request.url.query:
        target += "?" + request.url.query
    return RedirectResponse(target, status_code=307, headers={"cache-control": "no-store"})


def install_handoff_routes(app, legacy):
    from fastapi import Request

    @app.get("/sync-launch")
    async def launch(request: Request, path: str = "/woocommerce-product-sync", query: str = ""):
        if path not in TOOL_PATHS or len(query) > 2000:
            return JSONResponse({"error": "Herramienta inválida."}, status_code=400)
        session = legacy.SESSIONS.get(request.cookies.get("session_id"))
        if not session:
            return HTMLResponse("<h2>Conecta Google Drive primero.</h2><a href='/'>Volver a Suite e-commerce</a>", status_code=401)
        now = time.time()
        for key, item in list(_HANDOFFS.items()):
            if item[0] < now:
                _HANDOFFS.pop(key, None)
        if len(_HANDOFFS) >= 500:
            return JSONResponse({"error": "Servicio ocupado. Vuelve a intentar."}, status_code=503)
        ticket = secrets.token_urlsafe(32)
        # Only an opaque single-use ticket reaches the browser. Google/store
        # credentials are redeemed server-to-server with the shared HMAC key.
        _HANDOFFS[ticket] = (now + 120, session, path, query)
        return RedirectResponse(os.getenv("SYNC_SERVICE_URL", "").rstrip("/") +
            "/session/start?" + urlencode({"ticket": ticket}), status_code=303,
            headers={"cache-control": "no-store", "referrer-policy": "no-referrer"})

    @app.post("/sync-handoff/redeem")
    async def redeem(request: Request):
        raw = await request.body()
        if len(raw) > 1024 or not verify(raw, request.headers.get("x-suite-time"),
            request.headers.get("x-suite-nonce"), request.headers.get("x-suite-signature"),
            os.getenv("SYNC_SERVICE_SHARED_KEY", "")):
            return JSONResponse({"error": "No autorizado."}, status_code=401)
        try:
            ticket = json.loads(raw)["ticket"]
            item = _HANDOFFS.pop(ticket, None)
        except (ValueError, KeyError, TypeError):
            item = None
        if not item or item[0] < time.time():
            return JSONResponse({"error": "Acceso caducado. Abre la herramienta desde la Suite."}, status_code=401)
        try:
            context = await asyncio.to_thread(_worker_context, item[1], legacy)
            return JSONResponse({"context": context, "path": item[2], "query": item[3]},
                headers={"cache-control": "no-store"})
        except Exception:
            return JSONResponse({"error": "No pude conectar Drive. Vuelve a la Suite."}, status_code=502)


def worker_enabled():
    return os.getenv("SUITE_SERVICE_ROLE", "main").lower() != "sync" and bool(os.getenv("SYNC_SERVICE_URL", "").strip())


def _worker_context(session, legacy):
    # Refresh on the main service. The worker receives only the access token,
    # never the refresh token, OAuth client secret or Gemini API key.
    legacy._get_drive_service(session)
    folder_key = session.get("carpeta_raiz_id_manual")
    cached = session.get("_sync_worker_refs")
    if not cached or cached[0] != folder_key or time.monotonic() - cached[1] > 60:
        drive = legacy._get_drive_service(session)
        refs = legacy._preparar_estructura(drive, session)
        cached = (folder_key, time.monotonic(), refs)
        session["_sync_worker_refs"] = cached
    root, images, spreadsheet, _ = cached[2]
    return {
        "access_token": session["creds"]["token"],
        "spreadsheet_id": spreadsheet, "images_folder_id": images,
        "root_folder_id": root,
        "store": {k: os.getenv(k, "") for k in STORE_KEYS if os.getenv(k)},
    }


async def forward_tool(request, legacy):
    path = request.url.path.rstrip("/")
    if path not in TOOL_PATHS or request.method not in {"GET", "POST"}:
        return JSONResponse({"error": "Herramienta no disponible."}, status_code=404)
    sid = request.cookies.get("session_id")
    session = legacy.SESSIONS.get(sid) if sid else None
    if not session:
        if request.method == "GET":
            return HTMLResponse("<h2>Conecta Google Drive primero.</h2><a href='/'>Volver</a>", status_code=401)
        return JSONResponse({"error": "Sesión de Google requerida."}, status_code=401)
    base = os.getenv("SYNC_SERVICE_URL", "").rstrip("/")
    key = os.getenv("SYNC_SERVICE_SHARED_KEY", "")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or len(key) < 32:
        return JSONResponse({"error": "Falta configurar la conexión segura al servicio de sincronización."}, status_code=503)
    raw = await request.body()
    if len(raw) > 1_000_000:
        return JSONResponse({"error": "Solicitud demasiado grande."}, status_code=413)
    try:
        context = await asyncio.to_thread(_worker_context, session, legacy)
        envelope = {
            "method": request.method, "path": path, "query": request.url.query,
            "body": raw.decode("utf-8"), "context": context,
        }
        body = json.dumps(envelope, separators=(",", ":")).encode()
        timestamp, nonce = str(int(time.time())), secrets.token_urlsafe(24)
        headers = {
            "Content-Type": "application/json", "X-Suite-Time": timestamp,
            "X-Suite-Nonce": nonce, "X-Suite-Signature": signature(body, timestamp, nonce, key),
        }
        # No retries on writes: a timeout may follow an already successful PUT.
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15), follow_redirects=False) as client:
            result = await client.post(base + "/internal/tools", content=body, headers=headers)
        return Response(result.content, status_code=result.status_code, headers={
            "content-type": result.headers.get("content-type", "application/json"),
            "cache-control": "no-store", "x-suite-executor": "sync-service",
        })
    except httpx.TimeoutException:
        return JSONResponse({"error": "El segundo servicio tardó demasiado. Verifica el SKU antes de repetir la operación."}, status_code=504)
    except Exception:
        # Never echo exceptions containing credential-bearing requests.
        return JSONResponse({"error": "No pude conectar con el servicio de sincronización. Revisa Drive y vuelve a intentar."}, status_code=502)
