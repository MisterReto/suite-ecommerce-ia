"""Bounded, request-scoped product uploads. No daemon or detached jobs."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import os

from inventory_schema import is_variable_parent


def worker_limit(value=2):
    cap = max(1, min(4, int(os.getenv("BULK_MAX_WORKERS", "2"))))
    try:
        return max(1, min(cap, int(value)))
    except (ValueError, TypeError):
        raise ValueError("Los hilos deben ser un número entero.")


def plan_skus(inventory, selected):
    index = {}
    for row in inventory:
        sku = str(row.get("sku") or "").strip()
        if sku:
            if sku in index:
                raise ValueError(f"SKU duplicado en Sheets: {sku}")
            index[sku] = row
    chosen = set(selected)
    for sku in selected:
        if sku not in index:
            raise ValueError(f"SKU no encontrado en Sheets: {sku}")
        row = index[sku]
        if row.get("tipo") == "variation":
            parent = str(row.get("sku_padre") or "")
            if parent not in index or not is_variable_parent(index[parent]):
                raise ValueError(f"{sku}: falta su portada variable en Sheets.")
            if not row.get("atributo_nombre") or not row.get("atributo_valor"):
                raise ValueError(f"{sku}: faltan nombre y valor del atributo de variación.")
            chosen.add(parent)
    return sorted(chosen, key=lambda sku: (0 if is_variable_parent(index[sku]) else 2 if index[sku].get("tipo") == "variation" else 1, sku))


def next_wave(items, index, workers):
    pending = [item for item in items if item.get("status") in {"pending", "running"}]
    parents = [item for item in pending if is_variable_parent(index.get(item["sku"], {}))]
    candidates = parents or pending
    result, groups = [], set()
    for item in candidates:
        row = index.get(item["sku"], {})
        group = row.get("sku_padre") or item["sku"]
        if group not in groups:
            result.append(item)
            groups.add(group)
        if len(result) == workers:
            break
    return result


def run_wave(items, job, workers):
    # Fresh copied context per future preserves tenant store credentials.
    with ThreadPoolExecutor(max_workers=worker_limit(workers), thread_name_prefix="product-upload") as pool:
        futures = [pool.submit(copy_context().run, job, item) for item in items]
        return [future.result() for future in futures]


def parent_attributes(parent_sku, inventory):
    attributes = {}
    combinations = set()
    for row in inventory:
        if row.get("sku_padre") != parent_sku:
            continue
        name, option = str(row.get("atributo_nombre") or "").strip(), str(row.get("atributo_valor") or "").strip()
        if not name or not option:
            raise ValueError(f"Variación {row['sku']}: atributo incompleto.")
        if (name.casefold(), option.casefold()) in combinations:
            raise ValueError(f"{parent_sku}: dos variaciones usan el mismo atributo y valor.")
        combinations.add((name.casefold(), option.casefold()))
        attributes.setdefault(name, []).append(option)
    if not attributes:
        raise ValueError(f"{parent_sku}: no tiene variaciones con atributos.")
    if len(attributes) != 1:
        raise ValueError(f"{parent_sku}: las variaciones deben usar el mismo nombre de atributo.")
    return [{"name": name, "visible": True, "variation": True, "options": list(dict.fromkeys(options))}
        for name, options in attributes.items()]


def ensure_entity(wc, row, inventory, include_stock=False):
    sku, kind = row["sku"], row.get("tipo", "simple")
    if kind == "variation":
        parent = wc.find_product_by_sku(row.get("sku_padre", ""))
        if not parent or parent.get("type") != "variable":
            raise ValueError(f"{sku}: primero debe subirse correctamente su portada variable.")
        parent_id = int(parent["id"])
        matches = []
        for variation in wc.list_all_variations(parent_id):
            if str(variation.get("sku") or "").strip() == sku:
                matches.append(variation)
        if len(matches) > 1:
            raise ValueError(f"SKU duplicado en WooCommerce: {sku}")
        if matches:
            return dict(matches[0], _entity_type="variation", _parent_product_id=parent_id), False
        attribute = {"name": row["atributo_nombre"], "option": row["atributo_valor"]}
        prior = next((a for a in parent.get("attributes", []) if str(a.get("name", "")).casefold() == str(row["atributo_nombre"]).casefold()), None)
        if prior and prior.get("id"):
            attribute = {"id": prior["id"], "option": row["atributo_valor"]}
        payload = {"sku": sku, "status": "private", "attributes": [attribute]}
        endpoint = f"products/{parent_id}/variations"
    else:
        matches = [p for p in (wc.request("GET", "products", params={"sku": sku, "per_page": 100}) or []) if str(p.get("sku") or "").strip() == sku]
        if len(matches) > 1:
            raise ValueError(f"SKU duplicado en WooCommerce: {sku}")
        if matches:
            remote = matches[0]
            if remote.get("type") != kind:
                raise ValueError(f"{sku}: el tipo WooCommerce no coincide con Sheets; revisarlo antes de publicar.")
            return dict(remote, _entity_type="product", _parent_product_id=None), False
        payload = {"sku": sku, "name": row.get("nombre_producto") or sku, "type": kind, "status": "draft"}
        if is_variable_parent(row):
            payload.update(manage_stock=False, attributes=parent_attributes(sku, inventory))
        endpoint = "products"
        parent_id = None
    # New entities start as draft/private; they are published only after a
    # verified complete update. No retry of POST after a network timeout.
    payload["meta_data"] = [{"key": "_suite_bulk_created", "value": "1"}]
    entity = wc.request("POST", endpoint, payload=payload) or {}
    if entity.get("sku") != sku or not entity.get("id"):
        raise RuntimeError("WooCommerce no confirmó el SKU creado. Revisar antes de reintentar.")
    return dict(entity, _entity_type="variation" if kind == "variation" else "product", _parent_product_id=parent_id), True


def stock_is_placeholder(inventory):
    stocks = [r.get("Existencias") for r in inventory if not is_variable_parent(r)]
    return bool(stocks) and len(set(stocks)) == 1 and stocks[0] in (0, 1)


def publish_created(wc, entity, created):
    """A retry publishes our verified draft, without publishing other drafts."""
    owned = any(m.get("key") == "_suite_bulk_created" and str(m.get("value")) == "1"
        for m in entity.get("meta_data", []))
    if not (created or owned) or entity.get("status") == "publish":
        return
    if entity.get("_entity_type") == "variation":
        wc.update_variation(entity["_parent_product_id"], entity["id"], {"status": "publish"})
    else:
        wc.update_product(entity["id"], {"status": "publish"})
