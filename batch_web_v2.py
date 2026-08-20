"""Lotes WooCommerce v2: un SKU por petición HTTP, sin workers daemon.

El navegador encadena /batch-step. Si la pestaña se cierra o Render reinicia,
el progreso permanece en Google Sheets y el lote se puede reanudar.
"""
from __future__ import annotations

import asyncio
import gc
import html
import re
from threading import Lock

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
    processed_skus,
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


def _process_one(session, batch_id: str) -> dict:
    """Procesa exactamente un SKU. Nunca crea un thread de larga duración."""
    if not _STEP_LOCK.acquire(blocking=False):
        raise RuntimeError("Ya hay un producto procesándose. Espera a que termine.")
    _set_processing(batch_id)
    try:
        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        items = read_batch(sheets, spreadsheet_id, batch_id)
        # running se considera recuperable: puede venir de un reinicio anterior.
        item = next((r for r in items if str(r.get("status") or "") in {"pending", "running"}), None)
        if item is None:
            return {"done": True, "message": "No quedan SKU pendientes en este lote."}

        sku = str(item.get("sku") or "").strip()
        sheet_row = int(item["_sheet_row"])
        matches = [r for r in inventory if str(r.get("sku") or "").strip() == sku]
        if len(matches) != 1:
            update_batch_item(
                sheets, spreadsheet_id, sheet_row=sheet_row, status="error",
                message=f"Esperaba 1 fila para {sku}; encontré {len(matches)}.",
                finished_at=media_web.time.strftime("%Y-%m-%dT%H:%M:%S%z") if hasattr(media_web, "time") else "",
            )
            return {"done": False, "sku": sku, "status": "error"}
        row = matches[0]

        wc = WooCommerceClient()
        wp = WordPressMediaClient()
        if not wc.config.write_enabled:
            raise RuntimeError("WC_WRITE_ENABLED=false en Render.")
        if not wp.write_enabled:
            raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false en Render.")

        update_batch_item(
            sheets, spreadsheet_id, sheet_row=sheet_row,
            status="running", message="Resolviendo SKU en WooCommerce...",
            started_at=str(item.get("started_at") or "") or __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            finished_at="", permalink="",
        )

        # Primer paso puede tardar algunos segundos; después queda cacheado 30 min.
        wc_index, duplicates = catalog_by_sku_light(wc)
        if sku in duplicates:
            raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
        entity = wc_index.get(sku)
        if not entity:
            raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")

        update_batch_item(
            sheets, spreadsheet_id, sheet_row=sheet_row,
            status="running", message="Sincronizando imágenes Drive → WordPress...",
        )
        image_result = sync_one_product_images(
            row=row,
            drive_index=media_web._drive_index(session),
            media_cache=read_media_cache(sheets, spreadsheet_id),
            drive_factory=lambda: legacy_app._get_drive_service(session),
            sheets_service=sheets,
            spreadsheet_id=spreadsheet_id,
            wp_client=wp,
            wc_client=wc,
            wc_entity=entity,
            max_workers=1,
        )

        update_batch_item(
            sheets, spreadsheet_id, sheet_row=sheet_row,
            status="running", message="Actualizando contenido, categorías, precio y stock...",
        )
        product_result = sync_complete_product(
            row=row,
            wc_client=wc,
            wc_entity=entity,
            image_result=image_result,
        )
        if not product_result.get("backend_verified"):
            raise RuntimeError("La verificación posterior de WooCommerce no coincidió con el Sheet.")

        permalink = str(product_result.get("permalink") or "")
        update_batch_item(
            sheets, spreadsheet_id, sheet_row=sheet_row,
            status="success", message="Producto sincronizado y verificado.",
            finished_at=__import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            permalink=permalink,
        )
        return {"done": False, "sku": sku, "status": "success", "permalink": permalink}
    except Exception as exc:
        # Si ya logramos identificar la fila actual, registra el error y permite
        # que el navegador continúe con el siguiente SKU.
        try:
            if "sheets" in locals() and "spreadsheet_id" in locals() and "sheet_row" in locals():
                update_batch_item(
                    sheets, spreadsheet_id, sheet_row=sheet_row,
                    status="error", message=str(exc),
                    finished_at=__import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
                )
                return {"done": False, "sku": locals().get("sku", ""), "status": "error", "error": str(exc)}
        except Exception:
            pass
        raise
    finally:
        _set_processing(None)
        gc.collect()
        _STEP_LOCK.release()


def _reset_for_resume(session, batch_id: str) -> int:
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


@fastapi_app.get("/woocommerce-batch-sync", response_class=HTMLResponse)
def batch_page(request: Request):
    _, session = media_web._session(request)
    if not session:
        return HTMLResponse("<h2>Primero inicia sesión con Google Drive en la Suite.</h2><a href='/'>Volver</a>", status_code=401)

    wc = WooCommerceClient()
    wp = WordPressMediaClient()
    enabled = bool(wc.config.write_enabled and wp.write_enabled)
    disabled = "" if enabled else "disabled"
    gate = "✅ Escritura habilitada" if enabled else "⚠️ Activa WC_WRITE_ENABLED=true y WP_MEDIA_WRITE_ENABLED=true"

    body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sincronización por lotes</title><style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1250px;margin:auto}}.card{{background:#fff;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}.btn,button{{background:#172033;color:white;padding:11px 15px;border:0;border-radius:8px;text-decoration:none;cursor:pointer;margin:5px 6px 5px 0}}button:disabled{{opacity:.45;cursor:not-allowed}}textarea{{padding:10px;border:1px solid #cfd4dc;border-radius:8px;width:100%;min-height:80px;box-sizing:border-box}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.metric{{background:#f8fafc;border-radius:10px;padding:12px}}.metric b{{font-size:25px;display:block}}progress{{width:100%;height:24px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{background:#f2f4f7;position:sticky;top:0}}.table{{max-height:520px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}.success{{color:#087a37}}.error{{color:#b42318}}.running{{color:#175cd3}}.pending{{color:#667085}}
</style></head><body><div class='wrap'>
<h1>🚚 Sincronización WooCommerce por lotes</h1>
<div class='card'><a class='btn' href='/woocommerce-product-sync'>← 1 SKU</a><a class='btn' href='/inventory-manager'>Inventario</a><a class='btn' href='/woocommerce-image-preview'>Imágenes</a></div>
<div class='{'ok' if enabled else 'warn'}'><b>{html.escape(gate)}</b><br><b>Modo estable:</b> cada producto se procesa en una petición normal. Si cierras esta pestaña, el lote se pausa; al volver, pulsa Reanudar.</div>
<div class='card'><h2>Crear lote</h2><label><input type='checkbox' id='skip' checked> Omitir SKU incluidos en lotes anteriores</label><br><br>
<button {disabled} onclick='createBatch("10")'>Siguientes 10</button><button {disabled} onclick='createBatch("50")'>Siguientes 50</button><button {disabled} onclick='createBatch("all")'>Todos los pendientes</button>
<h3>Lote personalizado</h3><textarea id='custom' placeholder='SKU1, SKU2, SKU3...'></textarea><br><button {disabled} onclick='createBatch("custom")'>Sincronizar lista personalizada</button></div>
<div class='card'><h2>Progreso</h2><div><b>Lote:</b> <code id='batch-id'>—</code> <button id='resume' onclick='resumeBatch()'>Reanudar lote</button> <button id='pause' onclick='pauseBatch()'>Pausar</button></div><br>
<progress id='progress' max='100' value='0'></progress><div class='grid' style='margin-top:10px'><div class='metric'><b id='total'>0</b>Total</div><div class='metric'><b id='success'>0</b>✅ Correctos</div><div class='metric'><b id='errors'>0</b>❌ Errores</div><div class='metric'><b id='pending'>0</b>⏳ Pendientes</div></div><p id='state'>⚪ Pausado</p>
<div class='table'><table><thead><tr><th>#</th><th>SKU</th><th>Estado</th><th>Mensaje</th><th>Producto</th></tr></thead><tbody id='rows'></tbody></table></div></div>
</div><script>
let currentBatch=localStorage.getItem('wc_current_batch')||''; let running=false; let stopRequested=false;
if(currentBatch){{document.getElementById('batch-id').textContent=currentBatch; refreshStatus();}}
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function rowHtml(x){{var icon=x.status==='success'?'✅':x.status==='error'?'❌':x.status==='running'?'🔄':'⏳';var link=x.permalink?("<a href='"+esc(x.permalink)+"' target='_blank'>Abrir</a>"):'—';return '<tr><td>'+esc(x.position)+'</td><td><code>'+esc(x.sku)+'</code></td><td class="'+esc(x.status)+'">'+icon+' '+esc(x.status)+'</td><td>'+esc(x.message)+'</td><td>'+link+'</td></tr>';}}
async function refreshStatus(){{if(!currentBatch)return null;const r=await fetch('/batch-status?batch_id='+encodeURIComponent(currentBatch));const d=await r.json();if(!r.ok)return null;const s=d.summary;document.getElementById('total').textContent=s.total;document.getElementById('success').textContent=s.success;document.getElementById('errors').textContent=s.error;document.getElementById('pending').textContent=s.pending+s.running;document.getElementById('progress').value=s.total?((s.success+s.error)/s.total*100):0;document.getElementById('rows').innerHTML=d.rows.map(rowHtml).join('');return d;}}
async function createBatch(mode){{const body={{mode,skip_processed:document.getElementById('skip').checked,custom:document.getElementById('custom').value}};const r=await fetch('/batch-create',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const d=await r.json();if(!r.ok){{alert(d.error||'Error');return;}}currentBatch=d.batch_id;localStorage.setItem('wc_current_batch',currentBatch);document.getElementById('batch-id').textContent=currentBatch;await runLoop();}}
async function resumeBatch(){{if(!currentBatch){{alert('No hay lote seleccionado');return;}}const r=await fetch('/batch-resume',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:currentBatch}})}});const d=await r.json();if(!r.ok){{alert(d.error||'Error');return;}}await runLoop();}}
function pauseBatch(){{stopRequested=true;document.getElementById('state').textContent='🟡 Pausando al terminar el SKU actual...';}}
async function runLoop(){{if(running)return;running=true;stopRequested=false;document.getElementById('state').textContent='🟢 Procesando';try{{while(!stopRequested){{const st=await refreshStatus();if(!st)break;if((st.summary.pending+st.summary.running)===0)break;const r=await fetch('/batch-step',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:currentBatch}})}});const d=await r.json();await refreshStatus();if(!r.ok && r.status!==409){{console.log(d);}}if(d.done)break;await new Promise(res=>setTimeout(res,250));}}}}finally{{running=false;document.getElementById('state').textContent=stopRequested?'🟡 Pausado':'⚪ Lote detenido / terminado';await refreshStatus();}}}}
</script></body></html>"""
    return HTMLResponse(body)


@fastapi_app.post("/batch-create")
async def batch_create(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        mode = str(payload.get("mode") or "10")
        skip = bool(payload.get("skip_processed", True))
        custom = _parse_custom(payload.get("custom") or "")
        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        known = [str(r.get("sku") or "").strip() for r in inventory if str(r.get("sku") or "").strip()]
        known_set = set(known)
        already = processed_skus(sheets, spreadsheet_id) if skip else set()
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
        batch_id = create_batch(sheets, spreadsheet_id, selected)
        return {"ok": True, "batch_id": batch_id, "selected": len(selected)}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@fastapi_app.get("/batch-status")
def batch_status(request: Request, batch_id: str):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        data = _batch_payload(session, batch_id); data["ok"] = True; return data
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


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
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=409, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


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
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
