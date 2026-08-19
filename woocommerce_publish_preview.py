"""Preview seguro antes de publicar stock desde Google Sheets hacia WooCommerce.

No modifica WooCommerce. Clasifica cada SKU y revisa la configuración global
relacionada con productos agotados cuando la API la expone.
"""
from __future__ import annotations

from typing import Any

from woocommerce_client import WooCommerceClient


def inspect_out_of_stock_visibility(client: WooCommerceClient) -> dict[str, Any]:
    """Busca la preferencia de ocultar agotados de forma tolerante a versiones WC."""
    result = {
        "known": False,
        "hide_out_of_stock": None,
        "setting_id": None,
        "label": None,
        "raw_value": None,
        "warning": "No pude confirmar automáticamente la opción de ocultar productos agotados.",
    }
    try:
        groups = client.list_setting_groups()
    except Exception as exc:
        result["warning"] = f"No pude leer WooCommerce > Ajustes: {exc}"
        return result

    candidates: list[tuple[str, dict[str, Any]]] = []
    for group in groups or []:
        gid = str(group.get("id") or "").strip()
        if not gid:
            continue
        try:
            settings = client.list_settings(gid)
        except Exception:
            continue
        for item in settings or []:
            haystack = " ".join(
                str(item.get(k) or "") for k in ("id", "label", "description")
            ).casefold()
            if "out of stock" in haystack or "agotad" in haystack or "hide" in haystack and "stock" in haystack:
                candidates.append((gid, item))

    # Preferimos IDs conocidos/semánticamente claros, sin depender de uno solo.
    preferred = None
    for gid, item in candidates:
        sid = str(item.get("id") or "").casefold()
        if "hide_out_of_stock" in sid or ("hide" in sid and "stock" in sid):
            preferred = (gid, item)
            break
    if preferred is None and candidates:
        preferred = candidates[0]
    if preferred is None:
        return result

    gid, item = preferred
    raw = item.get("value")
    text = str(raw or "").strip().casefold()
    hide = text in {"yes", "true", "1", "on"}
    result.update({
        "known": True,
        "hide_out_of_stock": hide,
        "setting_id": item.get("id"),
        "label": item.get("label"),
        "raw_value": raw,
        "warning": (
            "WooCommerce está configurado para ocultar agotados; no publiques todos los ceros hasta cambiar esa opción."
            if hide else
            "WooCommerce no está configurado para ocultar agotados según la opción detectada."
        ),
    })
    return result


def build_stock_publish_preview(inventory_rows: list[dict[str, Any]], client: WooCommerceClient) -> dict[str, Any]:
    wc_index, duplicate_skus = client.catalog_by_sku(include_variations=True)
    rows = []
    counts = {
        "total_inventory": len(inventory_rows),
        "ready_product": 0,
        "ready_variation": 0,
        "missing": 0,
        "duplicate": 0,
        "blocked_variable_parent": 0,
    }

    duplicate_set = set(duplicate_skus.keys())
    for inv in inventory_rows:
        sku = str(inv.get("sku") or "").strip()
        stock = int(inv.get("Existencias", 0) or 0)
        wc = wc_index.get(sku)
        status = ""
        reason = ""
        entity_type = None
        product_id = None
        parent_id = None

        if sku in duplicate_set:
            status = "duplicate"
            reason = "El SKU aparece más de una vez en WooCommerce."
            counts["duplicate"] += 1
        elif wc is None:
            status = "missing"
            reason = "No existe este SKU en WooCommerce."
            counts["missing"] += 1
        else:
            entity_type = wc.get("_entity_type")
            product_id = wc.get("id")
            parent_id = wc.get("_parent_product_id")
            wc_type = str(wc.get("type") or "").strip().casefold()
            if entity_type == "variation":
                status = "ready_variation"
                reason = "Se puede publicar stock en esta variación."
                counts["ready_variation"] += 1
            elif wc_type == "variable":
                status = "blocked_variable_parent"
                reason = "Es un producto padre variable; el stock debe administrarse en sus variaciones."
                counts["blocked_variable_parent"] += 1
            else:
                status = "ready_product"
                reason = "Se puede publicar stock en este producto."
                counts["ready_product"] += 1

        rows.append({
            "sku": sku,
            "name": inv.get("nombre_producto", ""),
            "stock_to_publish": stock,
            "status": status,
            "reason": reason,
            "entity_type": entity_type,
            "product_id": product_id,
            "parent_product_id": parent_id,
        })

    return {
        "summary": counts,
        "visibility": inspect_out_of_stock_visibility(client),
        "duplicates": sorted(duplicate_set),
        "rows": rows,
    }
