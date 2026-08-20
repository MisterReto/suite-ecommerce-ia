"""UI de imágenes: preview rápido + prueba controlada de 1 SKU en segundo plano."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import html
import json
from threading import Lock
import time
import uuid

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount

import app as legacy_app
import publication_web
import server as integration_server
from inventory_operations import read_inventory
from wordpress_media import WordPressMediaClient
from woocommerce_client import WooCommerceClient
from woocommerce_image_sync import (
    IMAGES_FOLDER_ID,
    build_image_preview,
    list_drive_images,
    read_media_cache,
    sync_one_product_images,
)

fastapi_app = publication_web.fastapi_app
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = Lock()
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="image-sync-job")
_DRIVE_CACHE: dict[str, tuple[float, dict]] = {}
_DRIVE_CACHE_LOCK = Lock()
DRIVE_CACHE_TTL = 180


def _session(request: Request):
    sid = request.cookies.get("session_id")
    return (sid, legacy_app.SESSIONS.get(sid)) if sid else (None, None)


def _drive_index(session, force=False):
    key = f"{session.get('email','')}:{IMAGES_FOLDER_ID}"
    if not force:
        with _DRIVE_CACHE_LOCK:
            cached = _DRIVE_CACHE.get(key)
            if cached and time.time() - cached[0] < DRIVE_CACHE_TTL:
                return cached[1]
    drive = legacy_app._get_drive_service(session)
    index = list_drive_images(drive)
    with _DRIVE_CACHE_LOCK:
        _DRIVE_CACHE[key] = (time.time(), index)
    return index


def _render_rows(rows):
    out = []
    for row in rows:
        statuses = []
        for ref in row["images"]:
            if ref["resolution"] == "exact":
                icon = "✅"
            elif ref["resolution"] == "fallback":
                icon = "🔁"
            else:
                icon = "❌"
            label = ref["resolved_filename"] or ref["requested_filename"]
            statuses.append(f"{icon} {html.escape(label)}")
        if not statuses:
            statuses = ["— Sin nombres en columna imagenes"]
        wc_target = ""
        if row.get("wc_entity_type") == "variation":
            wc_target = f"Variación {row.get('wc_id')}"
        elif row.get("wc_id"):
            wc_target = f"Producto {row.get('wc_id')}"
        else:
            wc_target = "No encontrado"
        out.append(
            "<tr>"
            f"<td><code>{html.escape(row['sku'])}</code></td>"
            f"<td>{html.escape(str(row.get('name','')))}</td>"
            f"<td>{'<br>'.join(statuses)}</td>"
            f"<td>{html.escape(wc_target)}</td>"
            f"<td>{'✅ Listo' if row.get('ready') else '⚠️ Revisar'}</td>"
            "</tr>"
        )
    return "".join(out)


def _run_one_sku_job(job_id: str, session_id: str, sku: str):
    try:
        with _JOBS_LOCK:
            _JOBS[job_id].update({"status": "running", "message": "Leyendo inventario y medios..."})
        session = legacy_app.SESSIONS.get(session_id)
        if not session:
            raise RuntimeError("La sesión de Google expiró. Vuelve a iniciar sesión.")
        _, spreadsheet_id, _ = legacy_app._cargar_df(session)
        sheets = legacy_app._get_sheets_service(session)
        inventory = read_inventory(sheets, spreadsheet_id)
        matches = [row for row in inventory if str(row.get("sku") or "").strip() == sku]
        if len(matches) != 1:
            raise RuntimeError(f"Esperaba 1 fila para {sku}; encontré {len(matches)}.")
        row = matches[0]
        drive_index = _drive_index(session)
        media_cache = read_media_cache(sheets, spreadsheet_id)
        wc = WooCommerceClient()
        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)
        if sku in duplicates:
            raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
        entity = wc_index.get(sku)
        if not entity:
            raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")
        wp = WordPressMediaClient()
        with _JOBS_LOCK:
            _JOBS[job_id]["message"] = "Subiendo/reutilizando imágenes y asignándolas al SKU..."
        result = sync_one_product_images(
            row=row,
            drive_index=drive_index,
            media_cache=media_cache,
            drive_factory=lambda: legacy_app._get_drive_service(session),
            sheets_service=sheets,
            spreadsheet_id=spreadsheet_id,
            wp_client=wp,
            wc_client=wc,
            wc_entity=entity,
            max_workers=3,
        )
        with _JOBS_LOCK:
            _JOBS[job_id].update({"status": "done", "message": "Completado", "result": result})
    except Exception as exc:
        with _JOBS_LOCK:
            _JOBS[job_id].update({"status": "error", "message": str(exc)})


@fastapi_app.get("/wp-media-health")
def wp_media_health():
    try:
        return WordPressMediaClient().health()
    except Exception as exc:
        client = WordPressMediaClient()
        return JSONResponse(status_code=502, content={
            "ok": False, "error": str(exc), "configured": client.configured,
            "write_enabled": client.write_enabled, "url": client.base_url,
        })


@fastapi_app.get("/woocommerce-image-preview", response_class=HTMLResponse)
def image_preview(request: Request):
    sid, session = _session(request)
    if not session:
        return HTMLResponse("<h2>Primero inicia sesión con Google Drive en la Suite.</h2><a href='/'>Volver</a>", status_code=401)
    try:
        _, spreadsheet_id, _ = legacy_app._cargar_df(session)
        sheets = legacy_app._get_sheets_service(session)
        inventory = read_inventory(sheets, spreadsheet_id)
        drive_index = _drive_index(session)
        media_cache = read_media_cache(sheets, spreadsheet_id)
        wc = WooCommerceClient()
        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)
        payload = build_image_preview(inventory, drive_index, wc_index, duplicates, media_cache)
        s = payload["summary"]
        wp = WordPressMediaClient()
        wp_state = "✅ configurado" if wp.configured else "❌ faltan credenciales"
        gates = f"WC_WRITE_ENABLED={str(wc.config.write_enabled).lower()} · WP_MEDIA_WRITE_ENABLED={str(wp.write_enabled).lower()}"
        body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Preview imágenes</title>
<style>body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1500px;margin:auto}}.card,.metric{{background:white;border-radius:14px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}.card{{margin:14px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}.metric b{{font-size:28px;display:block}}.metric span{{font-size:13px;color:#667085}}.btn,button{{display:inline-block;background:#172033;color:white;padding:10px 14px;border-radius:8px;text-decoration:none;border:0;cursor:pointer;margin-right:8px}}input{{padding:10px;border:1px solid #cfd4dc;border-radius:8px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e6e8ec;text-align:left;vertical-align:top}}th{{background:#f2f4f7;position:sticky;top:0}}.table{{max-height:620px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}</style></head><body><div class='wrap'>
<h1>🖼️ Preview Drive → WordPress → WooCommerce</h1>
<div class='card'><a class='btn' href='/inventory-manager'>← Inventario</a><a class='btn' href='/woocommerce-publish-preview'>Stock</a><a class='btn' href='/wp-media-health' target='_blank'>Probar WordPress</a><p>Carpeta Drive: <code>{html.escape(IMAGES_FOLDER_ID)}</code> · WordPress: <b>{wp_state}</b><br><code>{html.escape(gates)}</code></p></div>
<div class='grid'><div class='metric'><b>{s['products']}</b><span>SKU</span></div><div class='metric'><b>{s['with_images']}</b><span>Con nombres de imagen</span></div><div class='metric'><b>{s['requested_files']}</b><span>Archivos solicitados</span></div><div class='metric'><b>{s['exact_files']}</b><span>Coincidencia exacta</span></div><div class='metric'><b>{s['fallback_files']}</b><span>Resueltos por patrón nuevo</span></div><div class='metric'><b>{s['missing_files']}</b><span>Faltantes Drive</span></div><div class='metric'><b>{s['already_uploaded']}</b><span>Ya registrados en Media Sync</span></div><div class='metric'><b>{s['ready_products']}</b><span>Productos listos</span></div></div>
<div class='card {'ok' if s['missing_files']==0 else 'warn'}'><b>{'✅' if s['missing_files']==0 else '⚠️'} Resolución de archivos</b><br>Los nombres legacy se sustituyen solo en tiempo de sincronización cuando existe el equivalente generado; el Sheet no se modifica.</div>
<div class='card'><h2>Prueba controlada de 1 SKU</h2><p>Este botón solo funcionará cuando <b>ambos</b> gates estén en true. Úsalo primero con un único SKU antes de cualquier lote.</p><input id='test-sku' placeholder='Ej. PANKAGR1KG'><button onclick='startJob()'>Subir y asignar 1 SKU</button><pre id='job'></pre></div>
<div class='card'><h2>Detalle</h2><div class='table'><table><thead><tr><th>SKU</th><th>Producto</th><th>Archivos</th><th>Destino WC</th><th>Estado</th></tr></thead><tbody>{_render_rows(payload['rows'])}</tbody></table></div></div>
</div><script>
let poll=null;async function startJob(){{const sku=document.getElementById('test-sku').value.trim();if(!sku){{alert('Escribe un SKU');return}};const r=await fetch('/image-sync-start',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{sku}})}});const d=await r.json();document.getElementById('job').textContent=JSON.stringify(d,null,2);if(r.ok)poll=setInterval(()=>checkJob(d.job_id),1000)}}async function checkJob(id){{const r=await fetch('/image-sync-status/'+id);const d=await r.json();document.getElementById('job').textContent=JSON.stringify(d,null,2);if(d.status==='done'||d.status==='error')clearInterval(poll)}}
</script></body></html>"""
        return HTMLResponse(body)
    except Exception as exc:
        return HTMLResponse(f"<h2>Error</h2><pre>{html.escape(str(exc))}</pre>", status_code=500)


@fastapi_app.post("/image-sync-start")
async def image_sync_start(request: Request):
    sid, session = _session(request)
    if not session or not sid:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        sku = str(payload.get("sku") or "").strip()
        if not sku:
            raise ValueError("SKU requerido.")
        wc = WooCommerceClient()
        wp = WordPressMediaClient()
        if not wc.config.write_enabled:
            raise ValueError("WC_WRITE_ENABLED sigue en false.")
        if not wp.write_enabled:
            raise ValueError("WP_MEDIA_WRITE_ENABLED sigue en false.")
        job_id = uuid.uuid4().hex
        with _JOBS_LOCK:
            _JOBS[job_id] = {"job_id": job_id, "sku": sku, "status": "queued", "message": "En cola"}
        _JOB_EXECUTOR.submit(_run_one_sku_job, job_id, sid, sku)
        return _JOBS[job_id]
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})


@fastapi_app.get("/image-sync-status/{job_id}")
def image_sync_status(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Job no encontrado"})
        return dict(job)


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
