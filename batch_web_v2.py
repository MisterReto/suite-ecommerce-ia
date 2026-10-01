"""Lotes WooCommerce v2: grupos de hilos por petición HTTP, sin workers daemon.

El navegador encadena /batch-step. Si la pestaña se cierra o Render reinicia,
el progreso permanece en Google Sheets y el lote se puede reanudar.
"""
from __future__ import annotations

import asyncio
import gc
import html
import re
from threading import Lock
from datetime import datetime
from bulk_product_upload import worker_limit, plan_skus, next_wave, run_wave, ensure_entity, parent_attributes, stock_is_placeholder, publish_created
from inventory_schema import is_variable_parent
from app_security import public_error
from woocommerce_media_prepare import prepare_product_media

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount

import app as legacy_app
import media_web
import product_web
from wordpress_media import WordPressMediaClient
from woocommerce_batch_sync import (
    batch_summary,
    create_batch,
    successful_skus,
    read_batch,
    update_batch_item,
)
from woocommerce_catalog_light import catalog_by_sku_light
from woocommerce_client import WooCommerceClient
from woocommerce_image_sync import read_media_cache, sync_one_product_images
from woocommerce_product_sync import sync_complete_product

fastapi_app = product_web.fastapi_app
_STEP_LOCK = Lock()
_STEP_STATE_LOCK = Lock()
_PROCESSING_BATCH: str | None = None


def _set_processing(batch_id: str | None):
    global _PROCESSING_BATCH
    with _STEP_STATE_LOCK:
        _PROCESSING_BATCH = batch_id


def _processing(batch_id: str) -> bool:
    with _STEP_STATE_LOCK:
        return _PROCESSING_BATCH == batch_id


def _parse_custom(value: str) -> list[str]:
    seen = set()
    out = []
    for raw in re.split(r"[,;\s]+", str(value or "")):
        sku = raw.strip()
        if sku and sku not in seen:
            seen.add(sku)
            out.append(sku)
    return out


def _batch_payload(session, batch_id: str) -> dict:
    spreadsheet_id, _, sheets = media_web._direct_inventory_context(session)
    rows = read_batch(sheets, spreadsheet_id, batch_id)
    return {
        "batch_id": batch_id,
        "processing": _processing(batch_id),
        "summary": batch_summary(rows),
        "rows": [
            {
                "position": r.get("position"),
                "sku": r.get("sku"),
                "status": r.get("status"),
                "message": r.get("message"),
                "started_at": r.get("started_at"),
                "finished_at": r.get("finished_at"),
                "permalink": r.get("permalink"),
            }
            for r in rows
        ],
    }


def _bool(value, default=False):
    return default if value in (None, "") else value is True or str(value).casefold() in {"true", "1", "yes"}



def _option_bool(payload, key, default):
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key}: debe ser verdadero o falso.")
    return value


def _process_one(session, batch_id: str) -> dict:
    """One HTTP request joins a bounded wave; closing the page pauses next wave."""
    if not _STEP_LOCK.acquire(blocking=False):
        raise RuntimeError("Ya hay un grupo de productos procesándose.")
    if not media_web._SYNC_LOCK.acquire(blocking=False):
        _STEP_LOCK.release()
        raise RuntimeError("Hay una sincronización individual en curso.")
    _set_processing(batch_id)
    try:
        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        items = read_batch(sheets, spreadsheet_id, batch_id)
        index = {r["sku"]: r for r in inventory}
        options = items[0] if items else {}
        images = _bool(options.get("include_images"), True)
        stock = _bool(options.get("include_stock"), False)
        workers = worker_limit(options.get("workers") or 2)
        if stock and stock_is_placeholder(inventory):
            raise ValueError("Las existencias parecen valores iniciales (todas 0 o 1). Registra el conteo físico o crea un lote sin publicar stock.")
        selected = next_wave(items, index, workers)
        if not selected:
            return {"done": True, "message": "Lote terminado."}
        drive_index = media_web._drive_index(session) if images else {}
        cache = read_media_cache(sheets, spreadsheet_id) if images else {}

        def job(item):
            # Every thread owns its Google HTTP services and Requests sessions.
            local_sheets = legacy_app._get_sheets_service(session)
            wc = WooCommerceClient()
            wp = WordPressMediaClient() if images else None
            sku, sheet_row = item["sku"], int(item["_sheet_row"])
            try:
                matches = [r for r in inventory if r["sku"] == sku]
                if len(matches) != 1:
                    raise ValueError(f"{sku}: se requiere una fila única en Sheets.")
                row = matches[0]
                if row.get("tipo") == "variation":
                    parent_item = next((i for i in items if i["sku"] == row.get("sku_padre")), None)
                    if parent_item and parent_item.get("status") != "success":
                        raise ValueError(f"{sku}: su portada falló; reanuda primero la portada.")
                if not wc.config.write_enabled or (images and not wp.write_enabled):
                    raise ValueError("La publicación está deshabilitada en el servicio.")
                update_batch_item(local_sheets, spreadsheet_id, sheet_row=sheet_row, status="running",
                    message="Creando/actualizando producto...", started_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                entity, created = ensure_entity(wc, row, inventory, stock)
                if is_variable_parent(row):
                    expected = parent_attributes(sku, inventory)
                    old = list(entity.get("attributes") or [])
                    for attribute in expected:
                        prior = next((a for a in old if str(a.get("name", "")).casefold() == attribute["name"].casefold()), None)
                        if prior:
                            attribute["options"] = list(dict.fromkeys(list(prior.get("options") or []) + attribute["options"]))
                            if prior.get("id"):
                                attribute["id"] = prior["id"]
                    names = {a["name"].casefold() for a in expected}
                    expected.extend(a for a in old if str(a.get("name", "")).casefold() not in names)
                    wc.update_product(int(entity["id"]), {"attributes": expected})
                image_result = prepare_product_media(row=row, drive_index=drive_index, media_cache=dict(cache),
                    drive_factory=lambda: legacy_app._get_drive_service(session), sheets_service=local_sheets,
                    spreadsheet_id=spreadsheet_id, wp_client=wp) if images else None
                result = sync_complete_product(row=row, wc_client=wc, wc_entity=entity,
                    image_result=image_result, verify_get=True, include_stock=stock)
                if not result.get("backend_verified"):
                    raise RuntimeError("La verificación posterior no coincide; revisar antes de reintentar.")
                publish_created(wc, entity, created)
                permalink = str(result.get("permalink") or entity.get("permalink") or "")
                update_batch_item(local_sheets, spreadsheet_id, sheet_row=sheet_row, status="success",
                    message="Creado y verificado." if created else "Actualizado y verificado.",
                    finished_at=datetime.now().astimezone().isoformat(timespec="seconds"), permalink=permalink)
                return {"sku": sku, "status": "success", "created": created}
            except Exception as exc:
                message = public_error(exc)
                update_batch_item(local_sheets, spreadsheet_id, sheet_row=sheet_row, status="error",
                    message=message, finished_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                return {"sku": sku, "status": "error", "error": message}
            finally:
                wc.session.close()
                if wp:
                    wp.session.close()
                if hasattr(local_sheets, "close"):
                    local_sheets.close()
        return {"done": False, "workers": workers, "results": run_wave(selected, job, workers)}
    finally:
        _set_processing(None)
        media_web._SYNC_LOCK.release()
        _STEP_LOCK.release()
        gc.collect()


def _reset_for_resume(session, batch_id: str) -> int:
    if not _STEP_LOCK.acquire(blocking=False):
        raise RuntimeError("Espera a que termine el grupo actual antes de reanudar.")
    try:
        spreadsheet_id, _, sheets = media_web._direct_inventory_context(session)
        rows = read_batch(sheets, spreadsheet_id, batch_id)
        if not rows:
            raise ValueError("No encontré ese lote.")
        reset = 0
        for row in rows:
            status = str(row.get("status") or "")
            if status in {"running", "error"}:
                update_batch_item(
                    sheets, spreadsheet_id, sheet_row=int(row["_sheet_row"]),
                    status="pending", message="Pendiente de reintento.",
                    started_at="", finished_at="", permalink="",
                )
                reset += 1
        return reset
    finally:
        _STEP_LOCK.release()


@fastapi_app.get("/woocommerce-batch-sync", response_class=HTMLResponse)
def batch_page(request: Request):
    _, session = media_web._session(request)
    if not session:
        return HTMLResponse("<h2>Primero inicia sesión con Google Drive en la Suite.</h2><a href='/'>Volver</a>", status_code=401)

    wc = WooCommerceClient()
    wp = WordPressMediaClient()
    enabled = bool(wc.config.write_enabled)
    disabled = "" if enabled else "disabled"
    gate = "✅ Escritura habilitada" if enabled else "⚠️ Activa WC_WRITE_ENABLED=true y WP_MEDIA_WRITE_ENABLED=true"

    body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sincronización por lotes</title><style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1250px;margin:auto}}.card{{background:#fff;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}.btn,button{{background:#172033;color:white;padding:11px 15px;border:0;border-radius:8px;text-decoration:none;cursor:pointer;margin:5px 6px 5px 0}}button:disabled{{opacity:.45;cursor:not-allowed}}textarea{{padding:10px;border:1px solid #cfd4dc;border-radius:8px;width:100%;min-height:80px;box-sizing:border-box}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.metric{{background:#f8fafc;border-radius:10px;padding:12px}}.metric b{{font-size:25px;display:block}}progress{{width:100%;height:24px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{background:#f2f4f7;position:sticky;top:0}}.table{{max-height:520px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}.success{{color:#087a37}}.error{{color:#b42318}}.running{{color:#175cd3}}.pending{{color:#667085}}
</style></head><body><div class='wrap'>
<h1>🚚 Subida masiva de productos</h1>
<div class='card'><a class='btn' href='/woocommerce-product-sync'>← 1 SKU</a><a class='btn' href='/inventory-hub'>Inventario</a><a class='btn' href='/woocommerce-image-preview'>Imágenes</a></div>
<div class='{'ok' if enabled else 'warn'}'><b>{html.escape(gate)}</b><br><b>Multihilos:</b> 2 productos simultáneos; primero portadas, después variaciones. Si cierras esta pestaña, el lote se pausa; al volver, pulsa Reanudar.</div>
<div class='card'><h2>Crear lote</h2><label>Hilos <select id='workers'><option>1</option><option selected>2</option></select></label><br><label><input id='images' type='checkbox' checked> Subir imágenes de Drive</label><br><label><input id='stock' type='checkbox'> Publicar existencias físicas de Sheets</label><p>Sin esta opción se conserva el stock de WooCommerce. Las portadas FULL no administran precio ni stock.</p><label><input type='checkbox' id='skip' checked> Omitir SKU subidos correctamente en lotes anteriores</label><br><br>
<button {disabled} onclick='createBatch("10")'>Siguientes 10</button><button {disabled} onclick='createBatch("50")'>Siguientes 50</button><button {disabled} onclick='createBatch("all")'>Todos los pendientes</button>
<h3>Lote personalizado</h3><textarea id='custom' placeholder='SKU1, SKU2, SKU3...'></textarea><br><button {disabled} onclick='createBatch("custom")'>Sincronizar lista personalizada</button></div>
<div class='card'><h2>Progreso</h2><div><b>Lote:</b> <code id='batch-id'>—</code> <button id='resume' onclick='resumeBatch()'>Reanudar lote</button> <button id='pause' onclick='pauseBatch()'>Pausar</button></div><br>
<progress id='progress' max='100' value='0'></progress><div class='grid' style='margin-top:10px'><div class='metric'><b id='total'>0</b>Total</div><div class='metric'><b id='success'>0</b>✅ Correctos</div><div class='metric'><b id='errors'>0</b>❌ Errores</div><div class='metric'><b id='pending'>0</b>⏳ Pendientes</div></div><p id='state'>⚪ Pausado</p>
<div class='table'><table><thead><tr><th>#</th><th>SKU</th><th>Estado</th><th>Mensaje</th><th>Producto</th></tr></thead><tbody id='rows'></tbody></table></div></div>
</div><script>
let currentBatch=localStorage.getItem('wc_current_batch')||''; let running=false; let stopRequested=false;
if(currentBatch){{document.getElementById('batch-id').textContent=currentBatch; refreshStatus();}}
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function rowHtml(x){{var icon=x.status==='success'?'✅':x.status==='error'?'❌':x.status==='running'?'🔄':'⏳';var link=String(x.permalink||'').startsWith('https://')?("<a href='"+esc(x.permalink)+"' target='_blank'>Abrir</a>"):'—';return '<tr><td>'+esc(x.position)+'</td><td><code>'+esc(x.sku)+'</code></td><td class="'+esc(x.status)+'">'+icon+' '+esc(x.status)+'</td><td>'+esc(x.message)+'</td><td>'+link+'</td></tr>';}}
async function refreshStatus(){{if(!currentBatch)return null;const r=await fetch('/batch-status?batch_id='+encodeURIComponent(currentBatch));const d=await r.json();if(!r.ok)return null;const s=d.summary;document.getElementById('total').textContent=s.total;document.getElementById('success').textContent=s.success;document.getElementById('errors').textContent=s.error;document.getElementById('pending').textContent=s.pending+s.running;document.getElementById('progress').value=s.total?((s.success+s.error)/s.total*100):0;document.getElementById('rows').innerHTML=d.rows.map(rowHtml).join('');return d;}}
async function createBatch(mode){{const body={{mode,skip_processed:document.getElementById('skip').checked,custom:document.getElementById('custom').value,workers:Number(document.getElementById('workers').value),include_images:document.getElementById('images').checked,include_stock:document.getElementById('stock').checked}};const r=await fetch('/batch-create',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const d=await r.json();if(!r.ok){{alert(d.error||'Error');return;}}currentBatch=d.batch_id;localStorage.setItem('wc_current_batch',currentBatch);document.getElementById('batch-id').textContent=currentBatch;await runLoop();}}
async function resumeBatch(){{if(!currentBatch){{alert('No hay lote seleccionado');return;}}const r=await fetch('/batch-resume',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:currentBatch}})}});const d=await r.json();if(!r.ok){{alert(d.error||'Error');return;}}await runLoop();}}
function pauseBatch(){{stopRequested=true;document.getElementById('state').textContent='🟡 Pausando al terminar el grupo actual...';}}
async function runLoop(){{if(running)return;running=true;stopRequested=false;document.getElementById('state').textContent='🟢 Procesando';try{{while(!stopRequested){{const st=await refreshStatus();if(!st)break;if((st.summary.pending+st.summary.running)===0)break;const r=await fetch('/batch-step',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:currentBatch}})}});const d=await r.json();await refreshStatus();if(!r.ok){{document.getElementById('state').textContent=d.error||'Lote pausado';stopRequested=d.error||'Lote pausado';break;}}if(d.done)break;await new Promise(res=>setTimeout(res,250));}}}}finally{{running=false;document.getElementById('state').textContent=typeof stopRequested==='string'?stopRequested:stopRequested?'🟡 Pausado':'⚪ Lote detenido / terminado';await refreshStatus();}}}}
</script></body></html>"""
    return HTMLResponse(body)



def _create_for_session(session, payload):
    if not isinstance(payload, dict):
        raise ValueError("La solicitud debe ser un objeto JSON.")
    mode = str(payload.get("mode") or "10")
    skip = _option_bool(payload, "skip_processed", True)
    custom = _parse_custom(payload.get("custom") or "")
    spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
    known = [str(r.get("sku") or "").strip() for r in inventory if str(r.get("sku") or "").strip()]
    known_set = set(known)
    already = successful_skus(sheets, spreadsheet_id) if skip else set()
    if mode == "custom":
        missing = [s for s in custom if s not in known_set]
        if missing:
            raise ValueError("SKU no encontrados: " + ", ".join(missing[:15]))
        selected = [s for s in custom if s not in already]
    else:
        candidates = [s for s in known if s not in already]
        selected = candidates[:10] if mode == "10" else candidates[:50] if mode == "50" else candidates if mode == "all" else []
    if not selected:
        raise ValueError("No quedan SKU para este lote.")
    selected = plan_skus(inventory, selected)
    images = _option_bool(payload, "include_images", True)
    stock = _option_bool(payload, "include_stock", False)
    if stock and stock_is_placeholder(inventory):
        raise ValueError("Registra existencias físicas antes de publicar stock; también puedes subir contenido sin stock.")
    batch_id = create_batch(sheets, spreadsheet_id, selected, include_images=images,
        include_stock=stock, workers=worker_limit(payload.get("workers", 2)))
    return {"ok": True, "batch_id": batch_id, "selected": len(selected)}

@fastapi_app.post("/batch-create")
async def batch_create(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        return await asyncio.to_thread(_create_for_session, session, payload)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": public_error(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": public_error(exc)})


@fastapi_app.get("/batch-status")
def batch_status(request: Request, batch_id: str):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        data = _batch_payload(session, batch_id); data["ok"] = True; return data
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": public_error(exc)})


@fastapi_app.post("/batch-step")
async def batch_step(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json(); batch_id = str(payload.get("batch_id") or "").strip()
        if not batch_id: raise ValueError("batch_id requerido")
        result = await asyncio.to_thread(_process_one, session, batch_id)
        return {"ok": True, **result}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": public_error(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=409, content={"ok": False, "error": public_error(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": public_error(exc)})


@fastapi_app.post("/batch-resume")
async def batch_resume(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json(); batch_id = str(payload.get("batch_id") or "").strip()
        if not batch_id: raise ValueError("batch_id requerido")
        reset = await asyncio.to_thread(_reset_for_resume, session, batch_id)
        return {"ok": True, "batch_id": batch_id, "reset": reset}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": public_error(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": public_error(exc)})


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
