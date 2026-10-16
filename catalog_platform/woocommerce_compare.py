"""Read-only inventory comparison by SKU, using the accepted Colab HTTP profile.

Product pages and each variable product's variations are read completely before a
comparison is returned. A failed page must never look like missing inventory.
"""
from collections import defaultdict
from datetime import datetime, timezone
import math

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def read_store(engine):
    session = engine.ns["wc_session"]
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"])))

    def pages(endpoint):
        rows, seen, expected_total = [], set(), None
        for page in range(1, 501):
            response = session.get(engine.ns["WC_API"] + "/" + endpoint,
                params={"status": "any", "per_page": 100, "page": page}, timeout=60)
            items = engine.ns["comprobar_respuesta"](response, endpoint)
            if not isinstance(items, list):
                raise ValueError("WooCommerce no devolvió una página de productos válida.")
            ids = [item.get("id") for item in items if isinstance(item, dict)]
            if (len(ids) != len(items) or any(not item for item in ids)
                    or len(set(ids)) != len(ids) or seen.intersection(ids)):
                raise ValueError("WooCommerce repitió o devolvió una página inválida. Actualiza la comparación.")
            seen.update(ids)
            rows.extend(items)
            if len(rows) > 20000:
                raise ValueError("El catálogo supera el límite de comparación de 20 000 registros.")
            total_pages = response.headers.get("X-WP-TotalPages")
            total = response.headers.get("X-WP-Total")
            if total is not None:
                try:
                    total = int(total)
                except (TypeError, ValueError):
                    raise ValueError("WooCommerce devolvió un total de productos inválido.") from None
                if total < 0 or total > 20000 or (expected_total is not None and expected_total != total):
                    raise ValueError("El catálogo cambió durante la lectura o supera el límite. Actualiza la comparación.")
                expected_total = total
            if total_pages is not None:
                try:
                    total_pages = int(total_pages)
                except (TypeError, ValueError):
                    raise ValueError("WooCommerce devolvió un total de páginas inválido.") from None
                if total_pages > 500 or total_pages < 0 or (not items and page < total_pages):
                    raise ValueError("No se pudo leer el catálogo completo de WooCommerce.")
                if page >= total_pages:
                    if expected_total is not None and len(rows) != expected_total:
                        raise ValueError("La lectura de WooCommerce está incompleta. Actualiza la comparación.")
                    return rows
            elif len(items) < 100:
                if expected_total is not None and len(rows) != expected_total:
                    raise ValueError("La lectura de WooCommerce está incompleta. Actualiza la comparación.")
                return rows
        raise ValueError("No se pudo leer el catálogo completo de WooCommerce.")

    products = pages("products")
    rows = []
    for product in products:
        if product.get("status") == "trash":
            continue
        rows.append(remote_row(product))
        if len(rows) > 20000:
            raise ValueError("El catálogo supera el límite de comparación de 20 000 registros.")
        if product.get("type") == "variable":
            for variant in pages(f"products/{product['id']}/variations"):
                if variant.get("status") != "trash":
                    rows.append(remote_row(variant, product))
                if len(rows) > 20000:
                    raise ValueError("El catálogo supera el límite de comparación de 20 000 registros.")
    return {"rows": rows, "checked_at": datetime.now(timezone.utc).isoformat(),
            "products": len([row for row in rows if row["kind"] != "variant"]),
            "variations": len([row for row in rows if row["kind"] == "variant"])}


def quantity(value):
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def remote_row(item, parent=None):
    status = item.get("status", "")
    effective_status = parent.get("status", "") if parent and status == "publish" else status
    visibility = (parent or item).get("catalog_visibility", "visible")
    inherited = bool(parent and item.get("manage_stock") == "parent")
    own_stock = item.get("manage_stock") is True
    return {"id": item["id"], "parent_id": parent["id"] if parent else None,
        "parent_sku": (parent or {}).get("sku", ""),
        "sku": str(item.get("sku", "")).strip(), "name": item.get("name") or (parent or {}).get("name", ""),
        "kind": "variant" if parent else "family" if item.get("type") == "variable" else "simple",
        "status": effective_status, "own_status": status, "visibility": visibility,
        "stock": quantity(parent.get("stock_quantity")) if inherited and parent.get("manage_stock") is True
            else quantity(item.get("stock_quantity")) if own_stock else None,
        "stock_inherited": inherited}


def compare(local_rows, remote_rows):
    """Exact SKU matches only; duplicate identities and unknown stocks stay explicit."""
    by_sku = defaultdict(list)
    for row in remote_rows:
        if row["sku"]:
            by_sku[row["sku"]].append(row)
    local_skus = {row["sku"] for row in local_rows}
    rows = []
    for local in local_rows:
        matches = by_sku.get(local["sku"], [])
        remote = matches[0] if len(matches) == 1 else None
        stock, delta = "unknown", None
        if not matches:
            publication = "missing_woocommerce"
        elif not remote or remote["kind"] != local["kind"] or (
                local["kind"] == "variant" and remote["parent_sku"] != local["parent_sku"]):
            publication = "conflict"
        elif remote["status"] == "publish":
            publication = "hidden" if remote["visibility"] == "hidden" else "published"
        elif remote["status"] == "draft":
            publication = "draft"
        else:
            publication = "other"
        if local["kind"] == "family":
            stock = "not_applicable"
        elif remote and publication != "conflict" and not remote["stock_inherited"] and local["stock"] is not None and remote["stock"] is not None:
            delta = remote["stock"] - local["stock"]
            stock = "same" if abs(delta) < 1e-9 else "different"
        rows.append({**local, "publication": publication, "stock_comparison": stock,
            "difference": delta, "woocommerce": remote, "matches": matches if publication == "conflict" else []})
    for remote in remote_rows:
        if not remote["sku"] or remote["sku"] not in local_skus:
            rows.append({"sku": remote["sku"], "name": remote["name"], "kind": remote["kind"],
                "parent_sku": remote["parent_sku"], "stock": None, "brand": "", "category": "",
                "publication": "missing_app" if remote["sku"] else "no_sku",
                "stock_comparison": "unknown", "difference": None, "woocommerce": remote, "matches": []})
    summary = {key: sum(row["publication"] == key for row in rows) for key in (
        "missing_woocommerce", "missing_app", "published", "draft", "hidden", "conflict", "other", "no_sku")}
    summary["stock_different"] = sum(row["stock_comparison"] == "different" for row in rows)
    return {"rows": rows, "summary": summary, "app_products": len(local_rows)}
