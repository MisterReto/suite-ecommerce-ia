"""Pipeline individual disparado al guardar un producto desde la Suite IA.

No procesa lotes. Lee exactamente el SKU recién guardado en `Lista completa` y:
- prepara/sube sus imágenes si existe el set generado;
- actualiza el producto/variación si el SKU ya existe en WooCommerce;
- crea un producto SIMPLE nuevo si el SKU todavía no existe.

Las variaciones nuevas se conservan en Lista completa pero no se inventa una
estructura padre/atributos de WooCommerce automáticamente.
"""
from __future__ import annotations

from typing import Any

from wordpress_media import WordPressMediaClient
from woocommerce_client import WooCommerceClient
from woocommerce_image_sync import read_media_cache
from woocommerce_media_prepare import prepare_product_media
from woocommerce_product_sync import (
    _pricing_and_stock,
    resolve_taxonomies,
    sync_complete_product,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _terms_payload(tax: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if tax.get("category_ids"):
        payload["categories"] = [{"id": int(x)} for x in tax["category_ids"]]
    if tax.get("tag_ids"):
        payload["tags"] = [{"id": int(x)} for x in tax["tag_ids"]]
    if tax.get("brand_ids"):
        payload["brands"] = [{"id": int(x)} for x in tax["brand_ids"]]
    return payload


def _create_simple(row: dict[str, Any], wc: WooCommerceClient, image_result: dict[str, Any]) -> dict[str, Any]:
    sku = _text(row.get("sku"))
    tax = resolve_taxonomies(wc, row)
    payload: dict[str, Any] = {
        "name": _text(row.get("nombre_producto")) or sku,
        "type": "simple",
        "status": "publish",
        "catalog_visibility": "visible",
        "sku": sku,
        "description": _text(row.get("descripcion_larga")),
        "short_description": _text(row.get("descripcion_corta")),
        **_pricing_and_stock(row),
        **_terms_payload(tax),
    }
    media_ids = [int(x) for x in (image_result or {}).get("assigned_media_ids", [])]
    if media_ids:
        payload["images"] = [{"id": media_id, "position": pos} for pos, media_id in enumerate(media_ids)]

    created = wc.request("POST", "products", payload=payload) or {}
    if _text(created.get("sku")) != sku:
        raise RuntimeError(f"WooCommerce creó el producto pero devolvió un SKU inesperado: {created.get('sku')}")
    return {
        "action": "created",
        "sku": sku,
        "product_id": created.get("id"),
        "permalink": created.get("permalink"),
        "backend_verified": True,
        "images": media_ids,
        "warnings": tax.get("warnings", []),
    }


def sync_saved_sku(session: dict[str, Any], sku: str) -> dict[str, Any]:
    """Sincroniza exclusivamente el SKU recién guardado por la interfaz IA."""
    # Imports tardíos para evitar ciclos durante el arranque FastAPI/Gradio.
    import app as runtime_app
    import media_web
    import server as integration_server

    spreadsheet_id, rows = integration_server._read_master_inventory(session)
    matches = [row for row in rows if _text(row.get("sku")) == _text(sku)]
    if len(matches) != 1:
        raise RuntimeError(f"Esperaba una fila para {sku} en Lista completa; encontré {len(matches)}.")
    row = matches[0]
    tipo = _text(row.get("tipo")).casefold()

    wc = WooCommerceClient()
    wp = WordPressMediaClient()
    if not wc.config.write_enabled:
        raise RuntimeError("WC_WRITE_ENABLED=false")
    if not wp.write_enabled:
        raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false")

    sheets = runtime_app._get_sheets_service(session)
    image_result = prepare_product_media(
        row=row,
        drive_index=media_web._drive_index(session),
        media_cache=read_media_cache(sheets, spreadsheet_id),
        drive_factory=lambda: runtime_app._get_drive_service(session),
        sheets_service=sheets,
        spreadsheet_id=spreadsheet_id,
        wp_client=wp,
    )

    # Simples se resuelven con una búsqueda puntual muy barata.
    entity = wc.find_product_by_sku(_text(sku))
    if entity:
        entity = dict(entity)
        entity["_entity_type"] = "product"
        entity["_parent_product_id"] = None
    elif tipo == "variation":
        # WooCommerce no ofrece una búsqueda global barata de variaciones por SKU;
        # solo en este caso usamos el índice completo para localizar una variación existente.
        wc_index, duplicates = wc.catalog_by_sku(include_variations=True)
        if _text(sku) in duplicates:
            raise RuntimeError(f"SKU duplicado en WooCommerce: {sku}")
        entity = wc_index.get(_text(sku))

    if entity:
        result = sync_complete_product(
            row=row,
            wc_client=wc,
            wc_entity=entity,
            image_result=image_result,
            verify_get=True,
        )
        result["action"] = "updated"
        result["image_sync"] = image_result
        return result

    if tipo == "variation":
        raise RuntimeError(
            "El SKU quedó guardado en Lista completa como variación, pero todavía no existe en WooCommerce. "
            "Descarga CSV 2 Variaciones e impórtalo para crear la relación con su producto padre."
        )
    if tipo == "variable":
        raise RuntimeError(
            "El producto padre variable quedó guardado, pero todavía no existe en WooCommerce. "
            "Descarga CSV 2 Variaciones e impórtalo junto con sus variaciones."
        )

    result = _create_simple(row, wc, image_result)
    result["image_sync"] = image_result
    return result
