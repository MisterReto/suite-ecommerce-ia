"""Índice SKU ligero para lotes de WooCommerce.

Evita descargar descripciones, imágenes y metadata de todos los productos. El
resultado se cachea 30 minutos. Cada thread de variaciones usa su propia sesión
HTTP para mantener keep-alive sin compartir estado mutable.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time
from typing import Any

from woocommerce_client import WooCommerceClient, WooCommerceError

_CACHE_LOCK = Lock()
_CACHE: dict[str, tuple[float, dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]] = {}
TTL_SECONDS = 1800
PRODUCT_FIELDS = "id,sku,name,type,manage_stock,stock_quantity,stock_status,regular_price,price,permalink"
VARIATION_FIELDS = "id,sku,manage_stock,stock_quantity,stock_status,regular_price,price"


def _slim(row: dict[str, Any], entity_type: str, parent_id: int | None = None) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "sku": row.get("sku", ""),
        "name": row.get("name", ""),
        "type": row.get("type"),
        "manage_stock": row.get("manage_stock"),
        "stock_quantity": row.get("stock_quantity"),
        "stock_status": row.get("stock_status"),
        "regular_price": row.get("regular_price"),
        "price": row.get("price"),
        "permalink": row.get("permalink"),
        "_entity_type": entity_type,
        "_parent_product_id": parent_id,
    }


def _pages(client: WooCommerceClient, endpoint: str, fields: str):
    for page in range(1, 100):
        rows = client.request(
            "GET",
            endpoint,
            params={"page": page, "per_page": 100, "_fields": fields},
        ) or []
        for row in rows:
            yield row
        if len(rows) < 100:
            break


def catalog_by_sku_light(client: WooCommerceClient, *, force: bool = False):
    key = client.config.base_url
    if not force:
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached and time.time() - cached[0] < TTL_SECONDS:
                return cached[1], cached[2]

    index: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, list[dict[str, Any]]] = {}
    variable_ids: list[int] = []

    def add(row: dict[str, Any], entity_type: str, parent_id: int | None = None):
        sku = str(row.get("sku") or "").strip()
        if not sku:
            return
        item = _slim(row, entity_type, parent_id)
        if sku in index:
            duplicates.setdefault(sku, [index[sku]]).append(item)
        else:
            index[sku] = item

    for product in _pages(client, "products", PRODUCT_FIELDS):
        add(product, "product")
        if product.get("type") == "variable" and product.get("id"):
            variable_ids.append(int(product["id"]))

    def fetch_variations(parent_id: int):
        local_client = WooCommerceClient(client.config)
        return parent_id, list(_pages(local_client, f"products/{parent_id}/variations", VARIATION_FIELDS))

    workers = min(3, len(variable_ids)) if variable_ids else 0
    if workers:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="wc-light") as executor:
            for start in range(0, len(variable_ids), workers):
                current = variable_ids[start:start + workers]
                futures = [executor.submit(fetch_variations, pid) for pid in current]
                for future in as_completed(futures):
                    try:
                        parent_id, variations = future.result()
                    except Exception as exc:
                        raise WooCommerceError(f"No pude leer variaciones: {exc}") from exc
                    for variation in variations:
                        add(variation, "variation", parent_id)
                futures.clear()

    with _CACHE_LOCK:
        _CACHE.clear()
        _CACHE[key] = (time.time(), index, duplicates)
    return index, duplicates


def clear_catalog_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
