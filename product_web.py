"""UI para sincronizar un producto completo de Lista completa hacia WooCommerce."""
from __future__ import annotations

import asyncio
import gc
import html

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount

import app as legacy_app
import media_web
from wordpress_media import WordPressMediaClient
from woocommerce_client import WooCommerceClient
from woocommerce_image_sync import read_media_cache, sync_one_product_images
from woocommerce_product_sync import sync_complete_product

fastapi_app = media_web.fastapi_app


def _full_sync(session, sku: str) -> dict:
    if not media_web._SYNC_LOCK.acquire(blocking=False):
        raise RuntimeError("Ya hay una sincronización en curso. Espera a que termine y vuelve a intentar.")
    try:
        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        matches = [row for row in inventory if str(row.get("sku") or "").strip() == sku]
        if len(matches) != 1:
            raise RuntimeError(f"Esperaba 1 fila para {sku}; encontré {len(matches)}.")
        row = matches[0]

        wc = WooCommerceClient()
        wp = WordPressMediaClient()
        if not wc.config.write_enabled:
            raise RuntimeError("WC_WRITE_ENABLED=false en Render.")
        if not wp.write_enabled:
            raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false en Render.")

        # Índice WooCommerce ligero y cacheado: determina si el SKU es producto o variación.
        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)
        if sku in duplicates:
            raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
        entity = wc_index.get(sku)
        if not entity:
            raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")

        # 1) Imágenes: reutiliza Media Sync y procesa una a la vez para RAM baja.
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

        # 2) Datos comerciales e inventario.
        product_result = sync_complete_product(
            row=row,
            wc_client=wc,
            wc_entity=entity,
            image_result=image_result,
        )
        if not product_result.get("backend_verified"):
            raise RuntimeError(
                "WooCommerce respondió a la actualización, pero la verificación posterior no coincide con el Sheet. "
                f"Resultado: {product_result}"
            )

        return {
            "sku": sku,
            "backend_verified": True,
            "image_sync": image_result,
            "product_sync": product_result,
            "source": {
                "name": row.get("nombre_producto"),
                "brand": row.get("Marca"),
                "category": row.get("categorias"),
                "price": row.get("precio"),
                "sale_price": row.get("Precio descuento"),
                "stock": row.get("Existencias"),
            },
        }
    finally:
        media_web._SYNC_LOCK.release()
        gc.collect()


@fastapi_app.get("/woocommerce-product-sync", response_class=HTMLResponse)
def product_sync_page(request: Request):
    _, session = media_web._session(request)
    if not session:
        return HTMLResponse("<h2>Primero inicia sesión con Google Drive en la Suite.</h2><a href='/'>Volver</a>", status_code=401)

    wc = WooCommerceClient()
    wp = WordPressMediaClient()
    enabled = bool(wc.config.write_enabled and wp.write_enabled)
    disabled = "" if enabled else "disabled"
    gate = (
        "✅ Escritura habilitada"
        if enabled
        else "⚠️ Activa WC_WRITE_ENABLED=true y WP_MEDIA_WRITE_ENABLED=true"
    )
    body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sincronizar producto completo</title><style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1050px;margin:auto}}.card{{background:#fff;border-radius:14px;padding:22px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}.btn,button{{background:#172033;color:white;padding:11px 15px;border:0;border-radius:8px;text-decoration:none;cursor:pointer;margin-right:8px}}button:disabled{{opacity:.45;cursor:not-allowed}}input{{padding:11px;border:1px solid #cfd4dc;border-radius:8px;min-width:250px}}pre{{background:#f2f4f7;padding:15px;border-radius:10px;white-space:pre-wrap;word-break:break-word}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}ul{{line-height:1.7}}
</style></head><body><div class='wrap'>
<h1>🔄 Sincronizar producto completo</h1>
<div class='card'><a class='btn' href='/woocommerce-image-preview'>← Imágenes</a><a class='btn' href='/inventory-manager'>Inventario</a><a class='btn' href='/woocommerce-publish-preview'>Preview stock</a></div>
<div class='{'ok' if enabled else 'warn'}'><b>{html.escape(gate)}</b><br>Esta operación modifica un solo SKU y después vuelve a leer WooCommerce para verificar el resultado.</div>
<div class='card'><h2>Qué sincroniza</h2><ul>
<li><b>Simple:</b> nombre, descripción corta/larga, precio, oferta, stock, categorías/subcategoría, etiquetas, marca e imágenes.</li>
<li><b>Variación:</b> precio, oferta, stock, descripción corta e imagen de la variación; categoría, etiquetas y marca se aplican al padre.</li>
<li>Los productos con stock 0 permanecen publicados pero agotados; la configuración de la tienda ya está en “no ocultar agotados”.</li>
</ul></div>
<div class='card'><h2>Prueba con 1 SKU</h2><input id='sku' value='FIDATB400G' placeholder='SKU'><button id='btn' {disabled} onclick='syncProduct()'>Sincronizar producto completo</button><pre id='result'>Esperando...</pre></div>
</div><script>
async function syncProduct(){{
 const sku=document.getElementById('sku').value.trim(); if(!sku){{alert('Escribe un SKU');return;}}
 const btn=document.getElementById('btn'); const out=document.getElementById('result');
 btn.disabled=true; btn.textContent='Sincronizando...'; out.textContent='Imágenes → categorías/tags/marca → contenido/precio/stock → verificación...';
 try{{
   const r=await fetch('/product-sync-one',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{sku}})}});
   const d=await r.json(); out.textContent=JSON.stringify(d,null,2);
   if(!r.ok) throw new Error(d.error||'Error');
   btn.textContent='✅ Producto actualizado';
 }}catch(e){{btn.disabled=false;btn.textContent='Sincronizar producto completo';}}
}}
</script></body></html>"""
    return HTMLResponse(body)


@fastapi_app.post("/product-sync-one")
async def product_sync_one(request: Request):
    _, session = media_web._session(request)
    if not session:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión de Google requerida."})
    try:
        payload = await request.json()
        sku = str(payload.get("sku") or "").strip()
        if not sku:
            raise ValueError("SKU requerido.")
        result = await asyncio.to_thread(_full_sync, session, sku)
        gc.collect()
        return {"ok": True, "message": "Producto completo sincronizado y verificado.", "result": result}
    except ValueError as exc:
        gc.collect()
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    except Exception as exc:
        gc.collect()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


_root_mounts = [r for r in fastapi_app.router.routes if isinstance(r, Mount) and getattr(r, "path", None) in {"", "/"}]
if _root_mounts:
    fastapi_app.router.routes[:] = [r for r in fastapi_app.router.routes if r not in _root_mounts] + _root_mounts
