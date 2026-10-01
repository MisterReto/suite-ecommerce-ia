"""Keep existing tool URLs, execute them on the second Render service."""
import asyncio
import json
import os
import secrets
import time
from urllib.parse import urlparse

import httpx
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sync_bridge_protocol import STORE_KEYS, TOOL_PATHS, signature


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
