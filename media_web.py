"""UI de imágenes: preview rápido + prueba controlada de 1 SKU.

La operación de escritura se ejecuta con asyncio.to_thread(): el request espera el
resultado final, pero el event loop de FastAPI/Gradio permanece libre. No usamos
jobs en memoria, evitando pérdidas de estado durante deploys/rolling restarts.
"""
from __future__ import annotations

import asyncio
import html
from threading import Lock
import time

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount

import app as legacy_app
import publication_web
import server as integration_server
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
_DRIVE_CACHE: dict[str, tuple[float, dict]] = {}
_DRIVE_CACHE_LOCK = Lock()
_SYNC_LOCK = Lock()
DRIVE_CACHE_TTL = 180


def _session(request: Request):
    sid = request.cookies.get("session_id")
    return (sid, legacy_app.SESSIONS.get(sid)) if sid else (None, None)


def _drive_index(session, force: bool = False):
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


def _direct_inventory_context(session):
    spreadsheet_id, rows = integration_server._read_master_inventory(session)
    sheets = legacy_app._get_sheets_service(session)
    return spreadsheet_id, rows, sheets


def _render_rows(rows):
    out = []
    for row in rows:
        statuses = []
        for ref in row["images"]:
            resolution = ref["resolution"]
            if resolution == "exact":
                icon = "✅"
            elif resolution == "fallback":
                icon = "🔁"
            elif resolution == "optional_legacy_missing":
                icon = "➖"
            else:
                icon = "❌"
            label = ref["resolved_filename"] or ref["requested_filename"]
            suffix = " (legacy opcional)" if resolution == "optional_legacy_missing" else ""
            statuses.append(f"{icon} {html.escape(label)}{suffix}")
        if not statuses:
            statuses = ["— Sin nombres en columna imagenes"]
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


def _sync_one_sku(session, sku: str) -> dict:
    if not _SYNC_LOCK.acquire(blocking=False):
        raise RuntimeError("Ya hay una sincronización de imágenes en curso. Espera a que termine y vuelve a intentar.")
    try:
        spreadsheet_id, inventory, sheets = _direct_inventory_context(session)
        matches = [row for row in inventory if str(row.get("sku") or "").strip() == sku]
        if len(matches) != 1:
            raise RuntimeError(f"Esperaba 1 fila para {sku}; encontré {len(matches)}.")
        row = matches[0]
        drive_index = _drive_index(session)
        media_cache = read_media_cache(sheets, spreadsheet_id)

        wc = WooCommerceClient()
        wp = WordPressMediaClient()
        if not wc.config.write_enabled:
            raise RuntimeError("WC_WRITE_ENABLED=false en el proceso de Render.")
        if not wp.write_enabled:
            raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false en el proceso de Render.")

        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)
        if sku in duplicates:
            raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
        entity = wc_index.get(sku)
        if not entity:
            raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")

        return sync_one_product_images(
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
    finally:
        _SYNC_LOCK.release()


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
    _, session = _session(request)
    if not session:
        return HTMLResponse("<h2>Primero inicia sesión con Google Drive en la Suite.</h2><a href='/'>Volver</a>", status_code=401)
    try:
        spreadsheet_id, inventory, sheets = _direct_inventory_context(session)
        drive_index = _drive_index(session)
        media_cache = read_media_cache(sheets, spreadsheet_id)
        wc = WooCommerceClient()
        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)
        payload = build_image_preview(inventory, drive_index, wc_index, duplicates, media_cache)
        s = payload["summary"]
        wp = WordPressMediaClient()

        both_enabled = bool(wc.config.write_enabled and wp.write_enabled)
        wp_state = "✅ configurado" if wp.configured else "❌ faltan credenciales"
        gates = f"WC_WRITE_ENABLED={str(wc.config.write_enabled).lower()} · WP_MEDIA_WRITE_ENABLED={str(wp.write_enabled).lower()}"
        gate_class = "ok" if both_enabled else "warn"
        gate_title = "✅ Escritura de prueba habilitada" if both_enabled else "⚠️ La prueba de escritura sigue bloqueada"
        disabled = "" if both_enabled else "disabled"

        body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Preview imágenes</title>
<style>body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1500px;margin:auto}}.card,.metric{{background:white;border-radius:14px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}.card{{margin:14px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}.metric b{{font-size:28px;display:block}}.metric span{{font-size:13px;color:#667085}}.btn,button{{display:inline-block;background:#172033;color:white;padding:10px 14px;border-radius:8px;text-decoration:none;border:0;cursor:pointer;margin-right:8px}}button:disabled{{opacity:.45;cursor:not-allowed}}input{{padding:10px;border:1px solid #cfd4dc;border-radius:8px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #e6e8ec;text-align:left;vertical-align:top}}th{{background:#f2f4f7;position:sticky;top:0}}.table{{max-height:620px;overflow:auto}}code{{background:#eef0f3;padding:2px 5px;border-radius:4px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}pre{{white-space:pre-wrap;word-break:break-word}}</style></head><body><div class='wrap'>
<h1>🖼️ Preview Drive → WordPress → WooCommerce</h1>
<div class='card'><a class='btn' href='/inventory-manager'>← Inventario</a><a class='btn' href='/woocommerce-publish-preview'>Stock</a><a class='btn' href='/wp-media-health' target='_blank'>Probar WordPress</a><p>Carpeta Drive: <code>{html.escape(IMAGES_FOLDER_ID)}</code> · WordPress: <b>{wp_state}</b></p></div>
<div class='{gate_class}'><b>{gate_title}</b><br><code>{html.escape(gates)}</code></div>
<div class='grid'><div class='metric'><b>{s['products']}</b><span>SKU</span></div><div class='metric'><b>{s['with_images']}</b><span>Con nombres de imagen</span></div><div class='metric'><b>{s['requested_files']}</b><span>Referencias en Sheet</span></div><div class='metric'><b>{s['exact_files']}</b><span>Coincidencia exacta</span></div><div class='metric'><b>{s['fallback_files']}</b><span>Resueltos por patrón nuevo</span></div><div class='metric'><b>{s['optional_legacy_missing']}</b><span>Legacy opcionales ignorados</span></div><div class='metric'><b>{s['missing_files']}</b><span>Faltantes obligatorios</span></div><div class='metric'><b>{s['already_uploaded']}</b><span>Ya registrados en Media Sync</span></div><div class='metric'><b>{s['ready_products']}</b><span>Productos listos</span></div></div>
<div class='card {'ok' if s['missing_files']==0 else 'warn'}'><b>{'✅' if s['missing_files']==0 else '⚠️'} Resolución de archivos</b><br>➖ significa una referencia antigua adicional que la app actual ya no genera; no bloquea si existen las tres imágenes canónicas.</div>
<div class='card'><h2>Prueba controlada de 1 SKU</h2><p>La petición espera el resultado final, pero la operación corre en un thread de servidor para no bloquear la Suite. Empieza con un SKU cuyo destino diga <b>Producto</b>, no Variación.</p><input id='test-sku' placeholder='Ej. HTBUVA238U'><button id='sync-btn' {disabled} onclick='syncOne()'>Subir y asignar 1 SKU</button><pre id='job'></pre></div>
<div class='card'><h2>Detalle</h2><div class='table'><table><thead><tr><th>SKU</th><th>Producto</th><th>Archivos</th><th>Destino WC</th><th>Estado</th></tr></thead><tbody>{_render_rows(payload['rows'])}</tbody></table></div></div>
</div><script>
async function syncOne(){{
 const sku=document.getElementById('test-sku').value.trim(); if(!sku){{alert('Escribe un SKU');return;}}
 const btn=document.getElementById('sync-btn'); const out=document.getElementById('job');
 btn.disabled=true; btn.textContent='Subiendo...'; out.textContent='Descargando de Drive, subiendo a WordPress y asignando en WooCommerce...';
 try{{
   const r=await fetch('/image-sync-one',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{sku}})}});
   const d=await r.json(); out.textContent=JSON.stringify(d,null,2);
   if(!r.ok) throw new Error(d.error||'Error de sincronización');
   btn.textContent='✅ Completado'; setTimeout(()=>location.reload(),1600);
 }}catch(e){{ btn.disabled=false; btn.textContent='Subir y asignar 1 SKU'; if(!out.textContent.includes('error')) out.textContent='❌ '+e.message; }}
}}
</script></body></html>"""
        return HTMLResponse(body)
    except Exception as exc:
        return HTMLResponse(f"<h2>Error</h2><pre>{html.escape(str(exc))}</pre>", status_code=500)


@fastapi_app.post("/image-sync-one")
async def image_sync_one(request: Request):
    _, session = _session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        sku = str(payload.get("sku") or "").strip()
        if not sku:
            raise ValueError("SKU requerido.")
        result = await asyncio.to_thread(_sync_one_sku, session, sku)
        return {"ok": True, "message": "Imágenes sincronizadas correctamente.", "result": result}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
