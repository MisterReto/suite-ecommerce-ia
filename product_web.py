"""UI para sincronizar un producto completo de Lista completa hacia WooCommerce."""
from __future__ import annotations

import asyncio
import gc
import html

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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


@fastapi_app.get("/woocommerce-product-sync")
def product_sync_page(request: Request):
    return RedirectResponse("/woocommerce-batch-sync", status_code=303)


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
