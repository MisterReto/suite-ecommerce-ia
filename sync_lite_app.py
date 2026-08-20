"""Servidor ligero y rápido para sincronización WooCommerce en Render Free.

No importa Gradio, Gemini, pandas ni PIL. Mantiene caches pequeños de catálogo,
Drive, inventario y Media Sync durante el lote y procesa un SKU por petición.
"""
from __future__ import annotations

import gc
import html
import json
import os
import re
import secrets
import time
from datetime import datetime
from threading import Lock

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
os.environ.setdefault("OAUTHLIB_IGNORE_SCOPE_CHANGE", "1")

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from inventory_operations import read_inventory
from wordpress_media import WordPressMediaClient
from woocommerce_batch_sync import (
    batch_summary,
    create_batch,
    processed_skus,
    read_batch,
    update_batch_item_fast,
)
from woocommerce_catalog_light import catalog_by_sku_light
from woocommerce_client import WooCommerceClient
from woocommerce_image_sync import IMAGES_FOLDER_ID, list_drive_images, read_media_cache
from woocommerce_media_prepare import prepare_product_media
from woocommerce_product_sync import sync_complete_product


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
SPREADSHEET_ID = os.environ.get(
    "INVENTORY_SPREADSHEET_ID",
    "1gnuDwcceWwN4ksNnyq3Hs_MQHTfnZQZjeLnph72aUrE",
).strip()

INVENTORY_CACHE_TTL = max(30, int(os.environ.get("SYNC_INVENTORY_CACHE_TTL", "300")))
DRIVE_CACHE_TTL = max(60, int(os.environ.get("SYNC_DRIVE_CACHE_TTL", "1800")))
MEDIA_CACHE_TTL = max(60, int(os.environ.get("SYNC_MEDIA_CACHE_TTL", "1800")))

DRIVE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive",
]
CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [GOOGLE_REDIRECT_URI] if GOOGLE_REDIRECT_URI else [],
    }
}

SESSIONS: dict[str, dict] = {}
app = FastAPI(title="Rincón de Asia Sync Lite")
_STEP_LOCK = Lock()
_CACHE_LOCK = Lock()

_INVENTORY_CACHE: tuple[float, list[dict] | None] = (0.0, None)
_DRIVE_INDEX_CACHE: tuple[float, dict | None] = (0.0, None)
_MEDIA_CACHE: tuple[float, dict | None] = (0.0, None)

# Un único cliente por proceso: mantiene conexiones HTTP keep-alive entre SKU.
WC_CLIENT = WooCommerceClient()
WP_CLIENT = WordPressMediaClient()


def _session(request: Request):
    sid = request.cookies.get("session_id")
    return SESSIONS.get(sid) if sid else None


def _credentials(session: dict) -> Credentials:
    creds = session.get("_credentials_obj")
    if creds is None:
        creds = Credentials.from_authorized_user_info(session["creds"], DRIVE_SCOPES)
        session["_credentials_obj"] = creds
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        session["creds"] = json.loads(creds.to_json())
    return creds


def _drive(session: dict):
    service = session.get("_drive_service")
    if service is None:
        service = build("drive", "v3", credentials=_credentials(session), cache_discovery=False)
        session["_drive_service"] = service
    return service


def _sheets(session: dict):
    service = session.get("_sheets_service")
    if service is None:
        service = build("sheets", "v4", credentials=_credentials(session), cache_discovery=False)
        session["_sheets_service"] = service
    return service


def _inventory_cached(session: dict, *, force: bool = False):
    global _INVENTORY_CACHE
    now = time.time()
    with _CACHE_LOCK:
        ts, rows = _INVENTORY_CACHE
        if not force and rows is not None and now - ts < INVENTORY_CACHE_TTL:
            return rows
    rows = read_inventory(_sheets(session), SPREADSHEET_ID)
    with _CACHE_LOCK:
        _INVENTORY_CACHE = (now, rows)
    return rows


def _drive_index_cached(session: dict, *, force: bool = False):
    global _DRIVE_INDEX_CACHE
    now = time.time()
    with _CACHE_LOCK:
        ts, index = _DRIVE_INDEX_CACHE
        if not force and index is not None and now - ts < DRIVE_CACHE_TTL:
            return index
    index = list_drive_images(_drive(session))
    with _CACHE_LOCK:
        _DRIVE_INDEX_CACHE = (now, index)
    return index


def _media_cache_cached(session: dict, *, force: bool = False):
    global _MEDIA_CACHE
    now = time.time()
    with _CACHE_LOCK:
        ts, cache = _MEDIA_CACHE
        if not force and cache is not None and now - ts < MEDIA_CACHE_TTL:
            return cache
    cache = read_media_cache(_sheets(session), SPREADSHEET_ID)
    with _CACHE_LOCK:
        _MEDIA_CACHE = (now, cache)
    return cache


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@app.get("/login")
def login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
        return PlainTextResponse("Faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI", status_code=500)
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=DRIVE_SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        autogenerate_code_verifier=False,
    )
    resp = RedirectResponse(auth_url)
    resp.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="lax", path="/", max_age=600)
    resp.set_cookie("oauth_code_verifier", flow.code_verifier or "", httponly=True, secure=True, samesite="lax", path="/", max_age=600)
    return resp


@app.get("/auth/callback")
def auth_callback(request: Request):
    try:
        params = dict(request.query_params)
        if "error" in params or "code" not in params:
            return PlainTextResponse(f"Google devolvió: {params}", status_code=400)
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=DRIVE_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI,
            state=request.cookies.get("oauth_state"),
        )
        flow.code_verifier = request.cookies.get("oauth_code_verifier")
        flow.fetch_token(code=params["code"])
        creds = flow.credentials
        sid = secrets.token_urlsafe(32)
        SESSIONS[sid] = {"creds": json.loads(creds.to_json()), "_credentials_obj": creds}
        resp = RedirectResponse("/woocommerce-batch-sync")
        resp.set_cookie("session_id", sid, httponly=True, secure=True, samesite="lax", path="/", max_age=60 * 60 * 24 * 30)
        resp.delete_cookie("oauth_state", path="/")
        resp.delete_cookie("oauth_code_verifier", path="/")
        return resp
    except Exception as exc:
        return PlainTextResponse(f"OAuth error: {exc}", status_code=500)


@app.get("/logout")
def logout(request: Request):
    sid = request.cookies.get("session_id")
    if sid:
        SESSIONS.pop(sid, None)
    resp = RedirectResponse("/")
    resp.delete_cookie("session_id", path="/")
    return resp


@app.get("/health")
def health():
    with _CACHE_LOCK:
        inventory_count = len(_INVENTORY_CACHE[1] or [])
        drive_count = len(_DRIVE_INDEX_CACHE[1] or {})
        media_count = len(_MEDIA_CACHE[1] or {})
    return {
        "ok": True,
        "mode": "sync-lite-fast",
        "spreadsheet_id": SPREADSHEET_ID,
        "images_folder_id": IMAGES_FOLDER_ID,
        "wc_write": WC_CLIENT.config.write_enabled,
        "wp_write": WP_CLIENT.write_enabled,
        "cache": {
            "inventory_rows": inventory_count,
            "drive_files": drive_count,
            "media_ids": media_count,
        },
    }


def _parse_custom(value: str) -> list[str]:
    seen = set()
    result = []
    for raw in re.split(r"[,;\s]+", str(value or "")):
        sku = raw.strip()
        if sku and sku not in seen:
            seen.add(sku)
            result.append(sku)
    return result


def _payload(session: dict, batch_id: str) -> dict:
    rows = read_batch(_sheets(session), SPREADSHEET_ID, batch_id)
    return {
        "batch_id": batch_id,
        "summary": batch_summary(rows),
        "rows": [
            {
                "position": r.get("position"),
                "sku": r.get("sku"),
                "status": r.get("status"),
                "message": r.get("message"),
                "permalink": r.get("permalink"),
            }
            for r in rows
        ],
    }


def _reset_resume(session: dict, batch_id: str) -> int:
    sheets = _sheets(session)
    rows = read_batch(sheets, SPREADSHEET_ID, batch_id)
    if not rows:
        raise ValueError("No encontré ese lote.")
    count = 0
    for row in rows:
        if str(row.get("status") or "") in {"running", "error"}:
            update_batch_item_fast(
                sheets,
                SPREADSHEET_ID,
                sheet_row=int(row["_sheet_row"]),
                status="pending",
                message="Pendiente de reintento.",
                started_at="",
                finished_at="",
                permalink="",
            )
            count += 1
    return count


def _process_one(session: dict, batch_id: str) -> dict:
    """Procesa un SKU usando caches de proceso y un solo PUT WooCommerce final."""
    if not _STEP_LOCK.acquire(blocking=False):
        raise RuntimeError("Ya hay un SKU procesándose. Espera a que termine.")
    sheets = _sheets(session)
    row_number = None
    sku = ""
    started = ""
    try:
        items = read_batch(sheets, SPREADSHEET_ID, batch_id)
        item = next((x for x in items if str(x.get("status") or "") in {"pending", "running"}), None)
        if item is None:
            return {"done": True}

        sku = str(item.get("sku") or "").strip()
        row_number = int(item["_sheet_row"])
        started = str(item.get("started_at") or "") or _now()
        update_batch_item_fast(
            sheets, SPREADSHEET_ID, sheet_row=row_number,
            status="running", message="Resolviendo SKU y caches...",
            started_at=started, finished_at="", permalink="",
        )

        inventory = _inventory_cached(session)
        matches = [r for r in inventory if str(r.get("sku") or "").strip() == sku]
        if len(matches) != 1:
            raise RuntimeError(f"Esperaba 1 fila para {sku}; encontré {len(matches)}.")
        source_row = matches[0]

        if not WC_CLIENT.config.write_enabled:
            raise RuntimeError("WC_WRITE_ENABLED=false")
        if not WP_CLIENT.write_enabled:
            raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false")

        wc_index, duplicates = catalog_by_sku_light(WC_CLIENT)
        if sku in duplicates:
            raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
        entity = wc_index.get(sku)
        if not entity:
            raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")

        update_batch_item_fast(
            sheets, SPREADSHEET_ID, sheet_row=row_number,
            status="running", message="Preparando/subiendo imágenes...",
            started_at=started, finished_at="", permalink="",
        )

        image_result = prepare_product_media(
            row=source_row,
            drive_index=_drive_index_cached(session),
            media_cache=_media_cache_cached(session),
            drive_factory=lambda: _drive(session),
            sheets_service=sheets,
            spreadsheet_id=SPREADSHEET_ID,
            wp_client=WP_CLIENT,
        )

        update_batch_item_fast(
            sheets, SPREADSHEET_ID, sheet_row=row_number,
            status="running", message="Actualizando producto completo...",
            started_at=started, finished_at="", permalink="",
        )
        product_result = sync_complete_product(
            row=source_row,
            wc_client=WC_CLIENT,
            wc_entity=entity,
            image_result=image_result,
            verify_get=False,
        )
        if not product_result.get("backend_verified"):
            raise RuntimeError("La respuesta de WooCommerce no coincidió con el Sheet.")

        permalink = str(product_result.get("permalink") or "")
        update_batch_item_fast(
            sheets, SPREADSHEET_ID, sheet_row=row_number,
            status="success", message="Producto sincronizado y verificado.",
            started_at=started, finished_at=_now(), permalink=permalink,
        )
        return {
            "done": False,
            "sku": sku,
            "status": "success",
            "permalink": permalink,
            "uploaded": image_result.get("uploaded", 0),
            "reused": image_result.get("reused", 0),
        }
    except Exception as exc:
        if row_number is not None:
            try:
                update_batch_item_fast(
                    sheets, SPREADSHEET_ID, sheet_row=row_number,
                    status="error", message=str(exc),
                    started_at=started, finished_at=_now(), permalink="",
                )
            except Exception:
                pass
            return {"done": False, "sku": sku, "status": "error", "error": str(exc)}
        raise
    finally:
        gc.collect()
        _STEP_LOCK.release()


@app.get("/")
def root(request: Request):
    return RedirectResponse("/woocommerce-batch-sync" if _session(request) else "/login")


@app.get("/woocommerce-batch-sync", response_class=HTMLResponse)
def batch_page(request: Request):
    session = _session(request)
    if not session:
        return HTMLResponse("<h2>Sesión de Google requerida</h2><p><a href='/login'>Conectar Google Drive</a></p>", status_code=401)
    enabled = bool(WC_CLIENT.config.write_enabled and WP_CLIENT.write_enabled)
    disabled = "" if enabled else "disabled"
    gate = "✅ Escritura habilitada" if enabled else "⚠️ Activa WC_WRITE_ENABLED y WP_MEDIA_WRITE_ENABLED"
    body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sync Lite Fast</title><style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:22px}}.wrap{{max-width:1250px;margin:auto}}.card{{background:white;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}button,.btn{{background:#172033;color:#fff;border:0;border-radius:8px;padding:10px 14px;margin:4px;cursor:pointer;text-decoration:none}}button:disabled{{opacity:.45}}textarea{{width:100%;min-height:75px;box-sizing:border-box}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.metric{{background:#f8fafc;padding:12px;border-radius:10px}}.metric b{{font-size:26px;display:block}}progress{{width:100%;height:24px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left}}.table{{max-height:520px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body><div class='wrap'>
<h1>🚚 Rincón de Asia · Sync Lite Fast</h1>
<div class='{'ok' if enabled else 'warn'}'><b>{html.escape(gate)}</b><br>Caches de Drive/Sheet + conexiones HTTP persistentes + un solo PUT WooCommerce por SKU.</div>
<div class='card'><a class='btn' href='/health' target='_blank'>Estado / caches</a><a class='btn' href='/logout'>Cerrar sesión</a></div>
<div class='card'><h2>Crear lote</h2><label><input type='checkbox' id='skip' checked> Omitir SKU incluidos en lotes anteriores</label><br><br><button {disabled} onclick='createBatch("10")'>Siguientes 10</button><button {disabled} onclick='createBatch("50")'>Siguientes 50</button><button {disabled} onclick='createBatch("all")'>Todos los pendientes</button><h3>Personalizado</h3><textarea id='custom' placeholder='SKU1, SKU2...'></textarea><br><button {disabled} onclick='createBatch("custom")'>Crear lote personalizado</button></div>
<div class='card'><h2>Progreso</h2><p>Lote: <code id='bid'>—</code> <button onclick='resumeBatch()'>Reanudar</button> <button onclick='pauseBatch()'>Pausar</button></p><progress id='bar' max='100' value='0'></progress><div class='grid'><div class='metric'><b id='total'>0</b>Total</div><div class='metric'><b id='success'>0</b>✅ Correctos</div><div class='metric'><b id='errors'>0</b>❌ Errores</div><div class='metric'><b id='pending'>0</b>⏳ Pendientes</div></div><p id='state'>⚪ Pausado</p><div class='table'><table><thead><tr><th>#</th><th>SKU</th><th>Estado</th><th>Mensaje</th><th>Producto</th></tr></thead><tbody id='rows'></tbody></table></div></div>
</div><script>
let batch=localStorage.getItem('wc_current_batch')||'';let running=false;let stop=false;if(batch){{document.getElementById('bid').textContent=batch;refresh();}}
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function row(x){{let i=x.status==='success'?'✅':x.status==='error'?'❌':x.status==='running'?'🔄':'⏳';let l=x.permalink?"<a target='_blank' href='"+esc(x.permalink)+"'>Abrir</a>":'—';return '<tr><td>'+esc(x.position)+'</td><td><code>'+esc(x.sku)+'</code></td><td>'+i+' '+esc(x.status)+'</td><td>'+esc(x.message)+'</td><td>'+l+'</td></tr>';}}
async function refresh(){{if(!batch)return null;let r=await fetch('/batch-status?batch_id='+encodeURIComponent(batch));let d=await r.json();if(!r.ok)return null;let s=d.summary;document.getElementById('total').textContent=s.total;document.getElementById('success').textContent=s.success;document.getElementById('errors').textContent=s.error;document.getElementById('pending').textContent=s.pending+s.running;document.getElementById('bar').value=s.total?((s.success+s.error)/s.total*100):0;document.getElementById('rows').innerHTML=d.rows.map(row).join('');return d;}}
async function createBatch(mode){{let b={{mode,skip_processed:document.getElementById('skip').checked,custom:document.getElementById('custom').value}};let r=await fetch('/batch-create',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(b)}});let d=await r.json();if(!r.ok){{alert(d.error||'Error');return;}}batch=d.batch_id;localStorage.setItem('wc_current_batch',batch);document.getElementById('bid').textContent=batch;runLoop();}}
async function resumeBatch(){{if(!batch){{alert('No hay lote');return;}}let r=await fetch('/batch-resume',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:batch}})}});let d=await r.json();if(!r.ok){{alert(d.error||'Error');return;}}runLoop();}}
function pauseBatch(){{stop=true;document.getElementById('state').textContent='🟡 Pausando al terminar el SKU actual...';}}
async function runLoop(){{if(running)return;running=true;stop=false;document.getElementById('state').textContent='🟢 Procesando';try{{let st=await refresh();while(!stop&&st&&(st.summary.pending+st.summary.running)>0){{let r=await fetch('/batch-step',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:batch}})}});let d=await r.json();st=await refresh();if(!r.ok){{document.getElementById('state').textContent='❌ '+(d.error||'Error');break;}}if(d.done)break;}}}}catch(e){{document.getElementById('state').textContent='❌ '+e.message;}}finally{{running=false;await refresh();if(stop)document.getElementById('state').textContent='🟡 Pausado';else document.getElementById('state').textContent='⚪ Lote terminado / detenido';}}}}
</script></body></html>"""
    return HTMLResponse(body)


@app.post("/batch-create")
async def batch_create(request: Request):
    session = _session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión requerida"})
    try:
        payload = await request.json()
        mode = str(payload.get("mode") or "10")
        skip = bool(payload.get("skip_processed", True))
        custom = _parse_custom(payload.get("custom") or "")
        inventory = _inventory_cached(session)
        sheets = _sheets(session)
        known = [str(r.get("sku") or "").strip() for r in inventory if str(r.get("sku") or "").strip()]
        known_set = set(known)
        already = processed_skus(sheets, SPREADSHEET_ID) if skip else set()
        if mode == "custom":
            missing = [s for s in custom if s not in known_set]
            if missing:
                raise ValueError("SKU inexistentes: " + ", ".join(missing[:15]))
            selected = [s for s in custom if s not in already]
        else:
            candidates = [s for s in known if s not in already]
            selected = candidates[:10] if mode == "10" else candidates[:50] if mode == "50" else candidates if mode == "all" else []
        if not selected:
            raise ValueError("No quedan SKU para este lote.")
        batch_id = create_batch(sheets, SPREADSHEET_ID, selected)
        return {"ok": True, "batch_id": batch_id, "selected": len(selected)}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.get("/batch-status")
def batch_status(request: Request, batch_id: str):
    session = _session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión requerida"})
    try:
        data = _payload(session, batch_id)
        data["ok"] = True
        return data
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/batch-resume")
async def batch_resume(request: Request):
    session = _session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión requerida"})
    try:
        payload = await request.json()
        batch_id = str(payload.get("batch_id") or "").strip()
        if not batch_id:
            raise ValueError("batch_id requerido")
        reset = _reset_resume(session, batch_id)
        return {"ok": True, "batch_id": batch_id, "reset": reset}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/batch-step")
async def batch_step(request: Request):
    session = _session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión requerida"})
    try:
        payload = await request.json()
        batch_id = str(payload.get("batch_id") or "").strip()
        if not batch_id:
            raise ValueError("batch_id requerido")
        result = _process_one(session, batch_id)
        result["ok"] = True
        return result
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})
