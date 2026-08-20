"""Sincronización completa por lotes con progreso persistente y RAM acotada."""
from __future__ import annotations

import gc
import html
import re
import threading
import time
from datetime import datetime, timezone

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
from woocommerce_client import WooCommerceClient
from woocommerce_image_sync import read_media_cache, sync_one_product_images
from woocommerce_product_sync import sync_complete_product

fastapi_app = product_web.fastapi_app

_BATCH_RUN_LOCK = threading.Lock()
_BATCH_STATE_LOCK = threading.Lock()
_ACTIVE_BATCH_ID: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _set_active(batch_id: str | None) -> None:
    global _ACTIVE_BATCH_ID
    with _BATCH_STATE_LOCK:
        _ACTIVE_BATCH_ID = batch_id


def _is_active(batch_id: str) -> bool:
    with _BATCH_STATE_LOCK:
        return _ACTIVE_BATCH_ID == batch_id


def _parse_custom_skus(value: str) -> list[str]:
    seen = set()
    out = []
    for raw in re.split(r"[,;\s]+", str(value or "")):
        sku = raw.strip()
        if sku and sku not in seen:
            seen.add(sku)
            out.append(sku)
    return out


def _run_batch(session, batch_id: str) -> None:
    """Worker único: un SKU a la vez, sin paralelizar imágenes ni productos."""
    try:
        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        inventory_by_sku = {}
        for row in inventory:
            sku = str(row.get("sku") or "").strip()
            if sku:
                inventory_by_sku.setdefault(sku, []).append(row)

        wc = WooCommerceClient()
        wp = WordPressMediaClient()
        if not wc.config.write_enabled:
            raise RuntimeError("WC_WRITE_ENABLED=false en Render.")
        if not wp.write_enabled:
            raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false en Render.")

        drive_index = media_web._drive_index(session)
        media_cache = read_media_cache(sheets, spreadsheet_id)
        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)

        items = read_batch(sheets, spreadsheet_id, batch_id)
        for item in items:
            if str(item.get("status") or "") == "success":
                continue

            sku = str(item.get("sku") or "").strip()
            sheet_row = int(item["_sheet_row"])
            started = _now()
            update_batch_item(
                sheets, spreadsheet_id, sheet_row=sheet_row,
                status="running", message="Sincronizando...", started_at=started,
                finished_at="", permalink="",
            )

            try:
                matches = inventory_by_sku.get(sku, [])
                if len(matches) != 1:
                    raise RuntimeError(f"Esperaba 1 fila para {sku}; encontré {len(matches)}.")
                if sku in duplicates:
                    raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
                entity = wc_index.get(sku)
                if not entity:
                    raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")
                row = matches[0]

                image_result = sync_one_product_images(
                    row=row,
                    drive_index=drive_index,
                    media_cache=media_cache,
                    drive_factory=lambda: legacy_app._get_drive_service(session),
                    sheets_service=sheets,
                    spreadsheet_id=spreadsheet_id,
                    wp_client=wp,
                    wc_client=wc,
                    wc_entity=entity,
                    max_workers=1,
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
                    started_at=started, finished_at=_now(), permalink=permalink,
                )
            except Exception as exc:
                update_batch_item(
                    sheets, spreadsheet_id, sheet_row=sheet_row,
                    status="error", message=str(exc),
                    started_at=started, finished_at=_now(), permalink="",
                )
            finally:
                gc.collect()
                time.sleep(0.15)

        inventory_by_sku.clear()
        media_cache.clear()
        wc_index.clear()
        duplicates.clear()
        gc.collect()
    except Exception as exc:
        try:
            spreadsheet_id, _, sheets = media_web._direct_inventory_context(session)
            for item in read_batch(sheets, spreadsheet_id, batch_id):
                if str(item.get("status") or "") == "success":
                    continue
                update_batch_item(
                    sheets, spreadsheet_id, sheet_row=int(item["_sheet_row"]),
                    status="error", message=f"Error global del lote: {exc}",
                    finished_at=_now(),
                )
        except Exception:
            pass
    finally:
        _set_active(None)
        gc.collect()
        _BATCH_RUN_LOCK.release()


def _start_worker(session, batch_id: str) -> None:
    if not _BATCH_RUN_LOCK.acquire(blocking=False):
        with _BATCH_STATE_LOCK:
            active = _ACTIVE_BATCH_ID
        raise RuntimeError(f"Ya hay un lote en ejecución: {active or 'otro lote'}")
    _set_active(batch_id)
    try:
        thread = threading.Thread(
            target=_run_batch,
            args=(session, batch_id),
            name=f"wc-batch-{batch_id[-8:]}",
            daemon=True,
        )
        thread.start()
    except Exception:
        _set_active(None)
        _BATCH_RUN_LOCK.release()
        raise


def _batch_payload(session, batch_id: str) -> dict:
    spreadsheet_id, _, sheets = media_web._direct_inventory_context(session)
    rows = read_batch(sheets, spreadsheet_id, batch_id)
    summary = batch_summary(rows)
    return {
        "batch_id": batch_id,
        "worker_active": _is_active(batch_id),
        "summary": summary,
        "rows": [
            {
                "position": row.get("position"),
                "sku": row.get("sku"),
                "status": row.get("status"),
                "message": row.get("message"),
                "started_at": row.get("started_at"),
                "finished_at": row.get("finished_at"),
                "permalink": row.get("permalink"),
            }
            for row in rows
        ],
    }


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
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1250px;margin:auto}}.card{{background:#fff;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}.btn,button{{background:#172033;color:white;padding:11px 15px;border:0;border-radius:8px;text-decoration:none;cursor:pointer;margin:5px 6px 5px 0}}button:disabled{{opacity:.45;cursor:not-allowed}}textarea,input{{padding:10px;border:1px solid #cfd4dc;border-radius:8px}}textarea{{width:100%;min-height:80px;box-sizing:border-box}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.metric{{background:#f8fafc;border-radius:10px;padding:12px}}.metric b{{font-size:25px;display:block}}progress{{width:100%;height:24px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{background:#f2f4f7;position:sticky;top:0}}.table{{max-height:520px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}.success{{color:#087a37}}.error{{color:#b42318}}.running{{color:#175cd3}}.pending{{color:#667085}}
</style></head><body><div class='wrap'>
<h1>🚚 Sincronización WooCommerce por lotes</h1>
<div class='card'><a class='btn' href='/woocommerce-product-sync'>← 1 SKU</a><a class='btn' href='/inventory-manager'>Inventario</a><a class='btn' href='/woocommerce-image-preview'>Imágenes</a></div>
<div class='{'ok' if enabled else 'warn'}'><b>{html.escape(gate)}</b><br>Procesa <b>un producto a la vez</b>. El progreso se guarda en <code>WooCommerce Batch Sync</code>, por lo que un reinicio puede reanudarse.</div>
<div class='card'><h2>Crear lote</h2><p>Los botones “siguientes” avanzan sobre SKU que aún no han sido incluidos en un lote. Los errores se vuelven a intentar con <b>Reanudar lote</b>.</p>
<label><input type='checkbox' id='skip' checked> Omitir SKU ya incluidos en lotes anteriores</label><br><br>
<button {disabled} onclick='createBatch("10")'>Sincronizar siguientes 10</button><button {disabled} onclick='createBatch("50")'>Siguientes 50</button><button {disabled} onclick='createBatch("all")'>Todos los pendientes</button>
<h3>O lote personalizado</h3><textarea id='custom' placeholder='SKU1, SKU2, SKU3...'></textarea><br><button {disabled} onclick='createBatch("custom")'>Sincronizar lista personalizada</button></div>
<div class='card'><h2>Progreso</h2><div><b>Lote:</b> <code id='batch-id'>—</code> <button onclick='resumeBatch()'>Reanudar lote</button></div><br>
<progress id='progress' max='100' value='0'></progress><div class='grid' style='margin-top:10px'><div class='metric'><b id='total'>0</b>Total</div><div class='metric'><b id='success'>0</b>✅ Correctos</div><div class='metric'><b id='errors'>0</b>❌ Errores</div><div class='metric'><b id='pending'>0</b>⏳ Pendientes</div></div><p id='worker'></p>
<div class='table'><table><thead><tr><th>#</th><th>SKU</th><th>Estado</th><th>Mensaje</th><th>Producto</th></tr></thead><tbody id='rows'></tbody></table></div></div>
</div><script>
let currentBatch=localStorage.getItem('wc_current_batch')||''; let pollTimer=null;
if(currentBatch){{document.getElementById('batch-id').textContent=currentBatch; startPolling();}}
async function createBatch(mode){{
 const reqBody={{mode:mode,skip_processed:document.getElementById('skip').checked,custom:document.getElementById('custom').value}};
 try{{const r=await fetch('/batch-create',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(reqBody)}});const d=await r.json();if(!r.ok)throw new Error(d.error||'Error');currentBatch=d.batch_id;localStorage.setItem('wc_current_batch',currentBatch);document.getElementById('batch-id').textContent=currentBatch;startPolling();}}catch(e){{alert(e.message);}}
}}
async function resumeBatch(){{if(!currentBatch){{alert('No hay lote seleccionado');return;}}try{{const r=await fetch('/batch-resume',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{batch_id:currentBatch}})}});const d=await r.json();if(!r.ok)throw new Error(d.error||'Error');startPolling();}}catch(e){{alert(e.message);}}}}
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function rowHtml(x){{var icon=x.status==='success'?'✅':x.status==='error'?'❌':x.status==='running'?'🔄':'⏳';var link=x.permalink?("<a href='"+esc(x.permalink)+"' target='_blank'>Abrir</a>"):'—';return '<tr><td>'+esc(x.position)+'</td><td><code>'+esc(x.sku)+'</code></td><td class="'+esc(x.status)+'">'+icon+' '+esc(x.status)+'</td><td>'+esc(x.message)+'</td><td>'+link+'</td></tr>';}}
async function refreshStatus(){{if(!currentBatch)return;try{{const r=await fetch('/batch-status?batch_id='+encodeURIComponent(currentBatch));const d=await r.json();if(!r.ok)return;const s=d.summary;document.getElementById('total').textContent=s.total;document.getElementById('success').textContent=s.success;document.getElementById('errors').textContent=s.error;document.getElementById('pending').textContent=s.pending+s.running;document.getElementById('progress').value=s.total?((s.success+s.error)/s.total*100):0;document.getElementById('worker').textContent=d.worker_active?'🟢 Worker activo':'⚪ Worker detenido / lote terminado';document.getElementById('rows').innerHTML=d.rows.map(rowHtml).join('');if(!d.worker_active && s.pending===0 && s.running===0){{clearInterval(pollTimer);pollTimer=null;}}}}catch(e){{}}}}
function startPolling(){{if(pollTimer)clearInterval(pollTimer);refreshStatus();pollTimer=setInterval(refreshStatus,3000);}}
</script></body></html>"""
    return HTMLResponse(body)


@fastapi_app.post("/batch-create")
async def batch_create_route(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        mode = str(payload.get("mode") or "10")
        skip_processed = bool(payload.get("skip_processed", True))
        custom = _parse_custom_skus(payload.get("custom") or "")

        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        known_skus = [str(row.get("sku") or "").strip() for row in inventory if str(row.get("sku") or "").strip()]
        known_set = set(known_skus)
        already = processed_skus(sheets, spreadsheet_id) if skip_processed else set()

        if mode == "custom":
            missing = [sku for sku in custom if sku not in known_set]
            if missing:
                raise ValueError("Estos SKU no existen en Lista completa: " + ", ".join(missing[:15]))
            selected = [sku for sku in custom if sku not in already]
        else:
            candidates = [sku for sku in known_skus if sku not in already]
            if mode == "10":
                selected = candidates[:10]
            elif mode == "50":
                selected = candidates[:50]
            elif mode == "all":
                selected = candidates
            else:
                raise ValueError("Modo de lote inválido.")

        if not selected:
            raise ValueError("No quedan SKU para este lote con los filtros seleccionados.")
        batch_id = create_batch(sheets, spreadsheet_id, selected)
        _start_worker(session, batch_id)
        return {"ok": True, "batch_id": batch_id, "selected": len(selected)}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=409, content={"ok": False, "error": str(exc)})


@fastapi_app.get("/batch-status")
def batch_status_route(request: Request, batch_id: str):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        data = _batch_payload(session, batch_id)
        data["ok"] = True
        return data
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@fastapi_app.post("/batch-resume")
async def batch_resume_route(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        batch_id = str(payload.get("batch_id") or "").strip()
        if not batch_id:
            raise ValueError("batch_id requerido")
        spreadsheet_id, _, sheets = media_web._direct_inventory_context(session)
        rows = read_batch(sheets, spreadsheet_id, batch_id)
        if not rows:
            raise ValueError("No encontré ese lote en WooCommerce Batch Sync.")
        if all(str(r.get("status") or "") == "success" for r in rows):
            return {"ok": True, "batch_id": batch_id, "message": "El lote ya está completamente correcto."}
        _start_worker(session, batch_id)
        return {"ok": True, "batch_id": batch_id, "message": "Lote reanudado."}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=409, content={"ok": False, "error": str(exc)})


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
