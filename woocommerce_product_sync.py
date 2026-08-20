"""Sincronización completa de un SKU desde Lista completa hacia WooCommerce.

Optimizada para lotes: taxonomías y padres variables se cachean, y en modo batch
la respuesta del PUT se usa para verificar sin hacer un GET adicional.
"""
from __future__ import annotations

import re
import time
from threading import Lock
from typing import Any

from inventory_schema import split_category_path
from woocommerce_client import WooCommerceClient, WooCommerceError

_TERM_CACHE: dict[tuple[str, str], tuple[float, dict[str, dict[str, Any]]]] = {}
_TERM_LOCK = Lock()
_TERM_TTL = 3600

_PARENT_LOCK = Lock()
_PARENT_TERM_SIGNATURE: dict[tuple[str, int], tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = {}
_PARENT_REMOTE_CACHE: dict[tuple[str, int], dict[str, Any]] = {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _key(value: Any) -> str:
    return _text(value).casefold()


def _money(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def parse_tags(value: Any) -> list[str]:
    seen = set()
    tags: list[str] = []
    for raw in re.split(r"[,;\n]+", _text(value)):
        tag = raw.strip()
        k = tag.casefold()
        if tag and k not in seen:
            seen.add(k)
            tags.append(tag)
    return tags


def _load_terms(client: WooCommerceClient, endpoint: str, *, force: bool = False) -> dict[str, dict[str, Any]]:
    cache_key = (client.config.base_url, endpoint)
    if not force:
        with _TERM_LOCK:
            cached = _TERM_CACHE.get(cache_key)
            if cached and time.time() - cached[0] < _TERM_TTL:
                return cached[1]

    result: dict[str, dict[str, Any]] = {}
    fields = "id,name,parent" if endpoint == "products/categories" else "id,name"
    for page in range(1, 100):
        rows = client.request(
            "GET", endpoint,
            params={"page": page, "per_page": 100, "_fields": fields},
        ) or []
        for row in rows:
            name = _text(row.get("name"))
            if name:
                result[_key(name)] = {
                    "id": int(row["id"]),
                    "name": name,
                    "parent": int(row.get("parent") or 0),
                }
        if len(rows) < 100:
            break
    with _TERM_LOCK:
        _TERM_CACHE[cache_key] = (time.time(), result)
    return result


def _remember_term(client: WooCommerceClient, endpoint: str, row: dict[str, Any]) -> None:
    cache_key = (client.config.base_url, endpoint)
    name = _text(row.get("name"))
    if not name:
        return
    slim = {"id": int(row["id"]), "name": name, "parent": int(row.get("parent") or 0)}
    with _TERM_LOCK:
        cached = _TERM_CACHE.get(cache_key)
        if cached:
            cached[1][_key(name)] = slim


def ensure_term(client: WooCommerceClient, endpoint: str, name: str, *, parent: int = 0) -> int:
    name = _text(name)
    if not name:
        raise ValueError("Nombre de término vacío")
    terms = _load_terms(client, endpoint)
    existing = terms.get(_key(name))
    if existing and (endpoint != "products/categories" or int(existing.get("parent") or 0) == int(parent)):
        return int(existing["id"])

    if endpoint == "products/categories":
        matches = client.request(
            "GET", endpoint,
            params={"search": name, "per_page": 100, "_fields": "id,name,parent"},
        ) or []
        for row in matches:
            if _key(row.get("name")) == _key(name) and int(row.get("parent") or 0) == int(parent):
                _remember_term(client, endpoint, row)
                return int(row["id"])

    payload: dict[str, Any] = {"name": name}
    if endpoint == "products/categories":
        payload["parent"] = int(parent)
    created = client.request("POST", endpoint, payload=payload)
    _remember_term(client, endpoint, created)
    return int(created["id"])


def resolve_taxonomies(client: WooCommerceClient, row: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    parent_name, child_name = split_category_path(row.get("categorias"))
    category_ids: list[int] = []
    parent_id = 0
    if parent_name:
        parent_id = ensure_term(client, "products/categories", parent_name, parent=0)
        category_ids.append(parent_id)
    if child_name:
        child_id = ensure_term(client, "products/categories", child_name, parent=parent_id)
        category_ids.append(child_id)

    tag_ids: list[int] = []
    for tag in parse_tags(row.get("etiquetas")):
        tag_ids.append(ensure_term(client, "products/tags", tag))

    brand_ids: list[int] = []
    brand = _text(row.get("Marca"))
    if brand:
        try:
            brand_ids.append(ensure_term(client, "products/brands", brand))
        except WooCommerceError as exc:
            warnings.append(f"No pude sincronizar la marca '{brand}': {exc}")

    return {
        "category_ids": category_ids,
        "tag_ids": tag_ids,
        "brand_ids": brand_ids,
        "warnings": warnings,
    }


def _pricing_and_stock(row: dict[str, Any]) -> dict[str, Any]:
    price = float(row.get("precio") or 0)
    sale = float(row.get("Precio descuento") or 0)
    stock = max(0, int(row.get("Existencias") or 0))
    return {
        "regular_price": f"{price:.2f}",
        "sale_price": f"{sale:.2f}" if sale > 0 and sale < price else "",
        "manage_stock": True,
        "stock_quantity": stock,
        "stock_status": "instock" if stock > 0 else "outofstock",
        "backorders": "no",
    }


def _parent_signature(tax: dict[str, Any]):
    return (
        tuple(tax["category_ids"]),
        tuple(tax["tag_ids"]),
        tuple(tax["brand_ids"]),
    )


def sync_complete_product(
    *,
    row: dict[str, Any],
    wc_client: WooCommerceClient,
    wc_entity: dict[str, Any],
    image_result: dict[str, Any] | None = None,
    verify_get: bool = True,
) -> dict[str, Any]:
    """Actualiza un SKU. En lotes, verify_get=False evita un GET redundante."""
    if not wc_client.config.write_enabled:
        raise RuntimeError("WC_WRITE_ENABLED=false")

    sku = _text(row.get("sku"))
    if not sku:
        raise ValueError("SKU vacío")

    tax = resolve_taxonomies(wc_client, row)
    categories = [{"id": cid} for cid in tax["category_ids"]]
    tags = [{"id": tid} for tid in tax["tag_ids"]]
    brands = [{"id": bid} for bid in tax["brand_ids"]]
    common_terms: dict[str, Any] = {}
    if categories:
        common_terms["categories"] = categories
    if tags:
        common_terms["tags"] = tags
    if brands:
        common_terms["brands"] = brands

    entity_type = wc_entity.get("_entity_type")
    assigned_images = list((image_result or {}).get("assigned_media_ids") or [])

    if entity_type == "variation":
        parent_id = int(wc_entity["_parent_product_id"])
        variation_id = int(wc_entity["id"])
        parent_key = (wc_client.config.base_url, parent_id)
        signature = _parent_signature(tax)

        remote_parent = None
        if common_terms:
            with _PARENT_LOCK:
                already = _PARENT_TERM_SIGNATURE.get(parent_key) == signature
                cached_parent = _PARENT_REMOTE_CACHE.get(parent_key)
            if not already:
                remote_parent = wc_client.update_product(parent_id, dict(common_terms))
                with _PARENT_LOCK:
                    _PARENT_TERM_SIGNATURE[parent_key] = signature
                    _PARENT_REMOTE_CACHE[parent_key] = remote_parent
            else:
                remote_parent = cached_parent

        variation_payload = _pricing_and_stock(row)
        short = _text(row.get("descripcion_corta"))
        if short:
            variation_payload["description"] = short
        if assigned_images:
            variation_payload["image"] = {"id": int(assigned_images[0])}

        remote = wc_client.update_variation(parent_id, variation_id, variation_payload)
        if verify_get:
            remote = wc_client.get_variation(parent_id, variation_id)
            remote_parent = wc_client.get_product(parent_id)
            with _PARENT_LOCK:
                _PARENT_REMOTE_CACHE[parent_key] = remote_parent
        elif remote_parent is None:
            with _PARENT_LOCK:
                remote_parent = _PARENT_REMOTE_CACHE.get(parent_key)
            if remote_parent is None:
                remote_parent = wc_client.get_product(parent_id)
                with _PARENT_LOCK:
                    _PARENT_REMOTE_CACHE[parent_key] = remote_parent

        verified = (
            _text(remote.get("sku")) == sku
            and _money(remote.get("regular_price")) == _money(row.get("precio"))
            and int(remote.get("stock_quantity") or 0) == max(0, int(row.get("Existencias") or 0))
        )
        if assigned_images:
            verified = verified and int((remote.get("image") or {}).get("id") or 0) == int(assigned_images[0])

        return {
            "sku": sku,
            "entity_type": "variation",
            "parent_product_id": parent_id,
            "variation_id": variation_id,
            "backend_verified": bool(verified),
            "permalink": (remote_parent or {}).get("permalink"),
            "regular_price": remote.get("regular_price"),
            "stock_quantity": remote.get("stock_quantity"),
            "stock_status": remote.get("stock_status"),
            "category_ids": [int(x.get("id")) for x in (remote_parent or {}).get("categories", [])],
            "tag_ids": [int(x.get("id")) for x in (remote_parent or {}).get("tags", [])],
            "brand_ids": [int(x.get("id")) for x in (remote_parent or {}).get("brands", [])],
            "warnings": tax["warnings"] + [
                "Producto variable: el nombre y la descripción larga del padre se preservaron para no sustituirlos con datos de una sola presentación."
            ],
        }

    product_id = int(wc_entity["id"])
    payload: dict[str, Any] = {
        "name": _text(row.get("nombre_producto")),
        "description": _text(row.get("descripcion_larga")),
        "short_description": _text(row.get("descripcion_corta")),
        **_pricing_and_stock(row),
        **common_terms,
    }
    if assigned_images:
        payload["images"] = [
            {"id": int(media_id), "position": pos}
            for pos, media_id in enumerate(assigned_images)
        ]

    remote = wc_client.update_product(product_id, payload)
    if verify_get:
        remote = wc_client.get_product(product_id)

    remote_image_ids = [int(x.get("id")) for x in remote.get("images", []) if x.get("id")]
    expected_stock = max(0, int(row.get("Existencias") or 0))
    verified = (
        _text(remote.get("sku")) == sku
        and _text(remote.get("name")) == _text(row.get("nombre_producto"))
        and _money(remote.get("regular_price")) == _money(row.get("precio"))
        and int(remote.get("stock_quantity") or 0) == expected_stock
    )
    if assigned_images:
        verified = verified and remote_image_ids[:len(assigned_images)] == [int(x) for x in assigned_images]

    return {
        "sku": sku,
        "entity_type": "product",
        "product_id": product_id,
        "backend_verified": bool(verified),
        "permalink": remote.get("permalink"),
        "name": remote.get("name"),
        "regular_price": remote.get("regular_price"),
        "sale_price": remote.get("sale_price"),
        "stock_quantity": remote.get("stock_quantity"),
        "stock_status": remote.get("stock_status"),
        "category_ids": [int(x.get("id")) for x in remote.get("categories", [])],
        "tag_ids": [int(x.get("id")) for x in remote.get("tags", [])],
        "brand_ids": [int(x.get("id")) for x in remote.get("brands", [])],
        "remote_image_ids": remote_image_ids,
        "date_modified_gmt": remote.get("date_modified_gmt"),
        "warnings": tax["warnings"],
    }
