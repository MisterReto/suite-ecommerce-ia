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


def _full_sync(session, sku: str, include_images: bool = False) -> dict:
    if not media_web._SYNC_LOCK.acquire(blocking=False):
        raise RuntimeError("Ya hay una sincronización en curso. Espera a que termine y vuelve a intentar.")
    try:
        spreadsheet_id, inventory, sheets = media_web._direct_inventory_context(session)
        matches = [row for row in inventory if str(row.get("sku") or "").strip() == sku]
        if len(matches) != 1:
            raise RuntimeError(f"Esperaba 1 fila para {sku}; encontré {len(matches)}.")
        row = matches[0]

        wc = WooCommerceClient()
        if not wc.config.write_enabled:
            raise RuntimeError("WC_WRITE_ENABLED=false en Render.")

        # Índice WooCommerce ligero y cacheado: determina si el SKU es producto o variación.
        entity = wc.find_entity_by_sku(sku, str(row.get("sku_padre") or ""))
        if not entity:
            raise RuntimeError(f"SKU no encontrado en WooCommerce: {sku}")

        if entity.get("type") == "variable":
            raise ValueError("Este SKU es una portada variable. Sincroniza el SKU de una variación para actualizar su precio y existencias.")

        # Images are opt-in: text/stock updates do not need a Drive image scan
        # or WordPress media credentials and preserve existing store images.
        image_result = None
        if include_images:
            wp = WordPressMediaClient()
            if not wp.write_enabled:
                raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false en Render.")
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
    enabled = bool(wc.config.write_enabled)
    disabled = "" if enabled else "disabled"
    gate = (
        "✅ Escritura habilitada"
        if enabled
        else "⚠️ Activa WC_WRITE_ENABLED=true"
    )
    body = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sincronizar producto completo</title><style>
body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#172033;margin:0;padding:24px}}.wrap{{max-width:1050px;margin:auto}}.card{{background:#fff;border-radius:14px;padding:22px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}}.btn,button{{background:#172033;color:white;padding:11px 15px;border:0;border-radius:8px;text-decoration:none;cursor:pointer;margin-right:8px}}button:disabled{{opacity:.45;cursor:not-allowed}}input{{padding:11px;border:1px solid #cfd4dc;border-radius:8px;min-width:250px}}pre{{background:#f2f4f7;padding:15px;border-radius:10px;white-space:pre-wrap;word-break:break-word}}.ok{{background:#eefbf3;border:1px solid #86d7a2;padding:14px;border-radius:10px}}.warn{{background:#fff7e8;border:1px solid #f5b84b;padding:14px;border-radius:10px}}ul{{line-height:1.7}}
@media(max-width:720px){{body{{padding:12px}}.card{{padding:14px}}.btn,button{{display:inline-block;box-sizing:border-box;max-width:100%;margin-bottom:8px;white-space:normal}}input:not([type=checkbox]){{box-sizing:border-box;min-width:0;width:100%;margin-bottom:10px}}input[type=checkbox]{{min-width:0}}}}
</style></head><body><div class='wrap'>
<h1>🔄 Sincronizar producto completo</h1>
<div class='card'><a class='btn' href='/woocommerce-image-preview'>← Imágenes</a><a class='btn' href='/inventory-manager'>Inventario</a><a class='btn' href='/woocommerce-publish-preview'>Preview stock</a></div>
<div class='{'ok' if enabled else 'warn'}'><b>{html.escape(gate)}</b><br>Esta operación modifica un solo SKU y después vuelve a leer WooCommerce para verificar el resultado.</div>
<div class='card'><h2>Qué sincroniza</h2><ul>
<li><b>Simple:</b> nombre, descripción corta/larga, precio, oferta, stock, categorías/subcategoría, etiquetas, marca e imágenes.</li>
<li><b>Variación:</b> precio, oferta, stock, descripción corta e imagen de la variación; categoría, etiquetas y marca se aplican al padre.</li>
<li>Los productos con stock 0 permanecen publicados pero agotados; la configuración de la tienda ya está en “no ocultar agotados”.</li>
</ul></div>
<div class='card'><h2>Sheets → WooCommerce · 1 SKU</h2><p>Actualiza datos y existencias desde Lista completa. Conserva las imágenes actuales salvo que marques la opción.</p><input id='sku' placeholder='SKU'><label><input id='include-images' type='checkbox' style='min-width:0'> Incluir imágenes de Drive (más lento)</label><p>La opción de imágenes requiere WP_MEDIA_WRITE_ENABLED=true.</p><button id='btn' {disabled} onclick='syncProduct()'>Sincronizar SKU</button><pre id='result' role='status' aria-live='polite'>Esperando...</pre></div>
</div><script>
async function syncProduct(){{
 const sku=document.getElementById('sku').value.trim(); if(!sku){{alert('Escribe un SKU');return;}}
 const btn=document.getElementById('btn'); const out=document.getElementById('result');
 btn.disabled=true; btn.textContent='Sincronizando...'; out.textContent='Leyendo SKU y verificando los cambios...';
 try{{
   const r=await fetch('/product-sync-one',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{sku,include_images:document.getElementById('include-images').checked}})}});
   const d=await r.json();
   if(!r.ok) throw new Error(d.error||'Error');
   out.textContent='✅ '+sku+' actualizado y verificado.';
   const warnings=d.result?.product_sync?.warnings||[];
   if(warnings.length) out.textContent+=String.fromCharCode(10)+warnings.join(String.fromCharCode(10));
 }}catch(e){{out.textContent='❌ '+e.message;}}
 finally{{btn.disabled=false;btn.textContent='Sincronizar SKU';}}
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
        include_images = payload.get("include_images", False)
        if not isinstance(include_images, bool):
            raise ValueError("include_images debe ser true o false.")
        result = await asyncio.to_thread(_full_sync, session, sku, include_images)
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
