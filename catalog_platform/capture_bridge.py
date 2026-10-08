"""Restore capture parity using the existing Sheet writer and catalog models.

Sheets remains the operational source during migration. SQL mirrors parent and
child in one transaction; a failed mirror is repairable without writing Sheets
again. Draft files are temporary Drive assets, scoped to store and actor.
"""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import uuid

from fastapi import HTTPException
from sqlalchemy import select, func
from catalog_capture import barcode_key, family_label, review_product, text
from catalog_capture import normalized, presentation
from .database import configured, transaction
from .models import Product, ProductImage, SyncEvent, AuditLog
from .accounts import account, put
from .security import member, unseal
from .catalog import save_product, audit
from .queue import request_lock


def root_for(value):
    return value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def active(value):
    return configured() and member(value.get("email", "")) and bool(root_for(value))


@contextmanager
def sheet_write_guard(value):
    """Serialize fresh-read + Sheet append across API processes for this store."""
    if active(value):
        with transaction() as db:
            request_lock(db, root_for(value), "capture-sheet-writer")
            yield
    else:
        yield


def candidate(product):
    return dict(sku=product["sku"], nombre_producto=product["name"], Marca=product["brand"],
                gramaje=product["size"], codigo_barras=product["barcode"], sku_padre=product["parent_sku"],
                atributo_nombre=product["attribute"], atributo_valor=product["attribute_value"])


def master_rows(value):
    if not active(value):
        return []
    with transaction() as db:
        records = list(db.scalars(select(Product).where(Product.tenant_id == root_for(value))))
        skus = {p.id: p.sku for p in records}
        pictures = {}
        for image in db.scalars(select(ProductImage).where(ProductImage.tenant_id == root_for(value))):
            pictures.setdefault(image.product_id, image.id)
        return [dict(sku=p.sku, tipo=p.product_type, sku_padre=skus.get(p.parent_id, ""),
                     nombre_producto=p.name, Marca=p.brand, gramaje=str(p.attributes.get("Tamaño", "")),
                     codigo_barras=p.barcode, precio=p.price, Existencias=p.stock,
                     categorias=p.category + (" > " + p.subcategory if p.subcategory else ""),
                     descripcion_corta=p.short_description, descripcion_larga=p.long_description,
                     etiquetas=", ".join(p.tags), atributo_nombre=next(iter(p.attributes), ""),
                     atributo_valor=next(iter(p.attributes.values()), ""), attributes=p.attributes,
                     _source="PostgreSQL", product_id=p.id,
                     image_url="/api/platform/images/" + pictures[p.id] if p.id in pictures else "")
                for p in records]


def woo_rows(value, product):
    from store_connection import drive_only
    from woocommerce_client import WooCommerceClient
    if drive_only():
        return [], "WooCommerce pausado por el modo solo Drive."
    # The existing store credentials are global; only the configured store may
    # use them. Never search another tenant's store with those credentials.
    store = os.getenv("WOOCOMMERCE_TENANT_ID") or os.getenv("WEBHOOK_TENANT_ID") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not store or store != root_for(value):
        return [], "WooCommerce no está asociado a esta tienda; no se consultó."
    client = WooCommerceClient()
    if not client.config.configured:
        return [], "WooCommerce no tiene una conexión configurada."
    entities = []
    parents = {}
    if product["sku"]:
        entity = client.find_entity_by_sku(product["sku"])
        if entity:
            parent_id = entity.get("parent_id") or entity.get("_parent_product_id")
            if entity.get("id"):
                if parent_id:
                    parent = client.get_product(int(parent_id))
                    parents[int(parent_id)] = parent
                    entity = dict(client.request("GET", f"products/{int(parent_id)}/variations/{int(entity['id'])}"), parent_id=int(parent_id))
                else:
                    entity = client.get_product(int(entity["id"]))
            entities.append(entity)
    if product["name"]:
        entities += client.request("GET", "products", params={"search": family_label(product["name"]), "per_page": 30})
    complete = True
    for parent in list(entities):
        if parent.get("type") != "variable" or not parent.get("id"):
            continue
        parents[int(parent["id"])] = parent
        for page in range(1, 4):
            children = client.request("GET", f"products/{int(parent['id'])}/variations", params={"page": page, "per_page": 100})
            entities += [dict(child, parent_id=int(parent["id"]), type="variation") for child in children]
            if len(children) < 100:
                break
        else:
            complete = False
    rows = []
    seen = set()
    for p in entities:
        identity = (p.get("parent_id"), p.get("id"), p.get("sku"))
        if identity in seen:
            continue
        seen.add(identity)
        parent = parents.get(p.get("parent_id"), {})
        attrs = {a.get("name", ""): a.get("option") or ", ".join(a.get("options", [])) for a in p.get("attributes", [])}
        meta = {m.get("key"): m.get("value") for m in p.get("meta_data", [])}
        images = p.get("images", []) or ([p["image"]] if p.get("image") else [])
        rows.append(dict(sku=p.get("sku", ""), nombre_producto=p.get("name", ""),
                         Marca=", ".join(b.get("name", "") for b in p.get("brands", parent.get("brands", []))) or str(meta.get("Marca", "")),
                         tipo=p.get("type", "variation" if p.get("parent_id") else "simple"),
                         sku_padre=parent.get("sku", ""), codigo_barras=p.get("global_unique_id") or meta.get("_barcode", ""),
                         gramaje=attrs.get("Tamaño", attrs.get("Presentación", "")),
                         precio=p.get("price"), attributes=attrs, atributo_nombre=next(iter(attrs), ""),
                         atributo_valor=next(iter(attrs.values()), ""),
                         image_url=images[0].get("src", "") if images else "", _source="WooCommerce"))
    return rows, "WooCommerce consultado en lectura (búsqueda acotada)." if complete else "Lectura de WooCommerce incompleta: revisa una familia con más de 300 variaciones antes de guardar."


def check(value, product, include_woo=False):
    from studio_api import runtime
    _, _, sheet_rows = runtime.captura.snapshot(value)
    rows = master_rows(value) + [dict(r, _source="Google Sheets") for r in sheet_rows]
    notes = []
    if include_woo:
        try:
            remote, note = woo_rows(value, product)
            rows += remote
            notes.append(note)
        except Exception:
            notes.append("No se pudo completar la lectura de WooCommerce. Verifica la conexión antes de crear una ficha.")
    result = review_product(rows, candidate(product))
    for row in rows:
        if not row.get("image_url") and text(row.get("imagenes")):
            from urllib.parse import quote
            row["image_url"] = "/api/matches/" + quote(text(row.get("sku")), safe="") + "/image"
        matches, differences = [], []
        for label, wanted, found in (("Marca", product["brand"], row.get("Marca")),
                                     ("Familia", family_label(product["name"]), family_label(row.get("nombre_producto"))),
                                     ("Presentación", product["size"], row.get("gramaje") or row.get("nombre_producto")),
                                     (product["attribute"], product["attribute_value"], row.get("atributo_valor"))):
            if not text(wanted) or not text(found):
                continue
            if (presentation(wanted) == presentation(found) if label == "Presentación" else normalized(wanted) == normalized(found)):
                matches.append(label)
            else:
                differences.append(f"{label}: {text(found)} / {wanted}")
        row["matching_attributes"], row["different_attributes"] = matches, differences
    result["sources"] = notes
    result["complete"] = not any("No se pudo" in n or "incompleta" in n for n in notes)
    return result


def checkpoint(value, current):
    if not configured() or not member(value.get("email", "")):
        return
    from studio_api import runtime, file_path
    from drive_service import DriveService
    drive = DriveService.for_session(runtime, value)
    root = root_for(value) or drive.root_id
    if root != drive.root_id:
        raise ValueError("La carpeta de la captura cambió. No se guardó el borrador en otra tienda.")
    value["carpeta_raiz_id_manual"] = root
    folder = None
    stored = current.setdefault("_persisted_files", {})

    def store_path(path):
        nonlocal folder
        checksum = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if checksum not in stored:
            if folder is None:
                actor = hashlib.sha256(value["email"].casefold().encode()).hexdigest()[:24]
                folder = drive.working_folder("capturas_temporales", actor, current["revision"])
            stored[checksum] = drive.upload(path, checksum + ".jpg", folder,
                                          {"capture_revision": current["revision"]})["id"]
        return stored[checksum]

    state = {k: deepcopy(v) for k, v in current.items() if k not in
             {"references", "images", "front_id", "back_id", "cover_id", "cover_token", "_persisted_files"}}
    state["references"] = [store_path(path) for path in current["references"]]
    state["images"] = {}
    for slot, image in current["images"].items():
        item = {k: deepcopy(v) for k, v in image.items() if k not in {"id", "raw_id"}}
        for key in ("id", "raw_id"):
            if image.get(key):
                item[key] = store_path(file_path(value, image[key]))
        state["images"][slot] = item
    if current.get("cover_id"):
        cover = value.get("family_covers", {}).get(current.get("cover_token"), {})
        state["cover"] = {k: v for k, v in cover.items() if k != "path"}
        state["cover"].update(file_id=store_path(file_path(value, current["cover_id"])), token=current.get("cover_token"))
    with transaction() as db:
        put(db, root, value["email"], "capture_draft", state)


def restore(value):
    if value.get("studio_draft") or not active(value):
        return
    with transaction() as db:
        record = account(db, root_for(value), value["email"], "capture_draft")
        if not record or record.status != "connected":
            return
        state = unseal(record.encrypted_credentials)
    from studio_api import runtime, asset
    from drive_service import DriveService
    from .worker import download_reference
    drive = DriveService.for_session(runtime, value)
    if drive.root_id != root_for(value):
        raise ValueError("No se puede recuperar un borrador de otra tienda.")
    current = deepcopy(state)
    stored = {}

    def local(key):
        path = f"/tmp/{value['file_namespace']}_draft_{hashlib.sha256(key.encode()).hexdigest()[:24]}.jpg"
        download_reference(drive, key, path)
        stored[hashlib.sha256(Path(path).read_bytes()).hexdigest()] = key
        return path

    current["references"] = [local(key) for key in state["references"]]
    current["front_id"] = asset(value, current["references"][0])
    current["back_id"] = asset(value, current["references"][1]) if len(current["references"]) > 1 else None
    for image in current["images"].values():
        for key in ("id", "raw_id"):
            if image.get(key):
                image[key] = asset(value, local(image[key]))
    if state.get("cover"):
        cover = dict(state["cover"])
        cover["path"] = local(cover.pop("file_id"))
        token = cover.pop("token")
        value.setdefault("family_covers", {})[token] = cover
        current.update(cover_id=asset(value, cover["path"]), cover_token=token)
    current["_persisted_files"] = stored
    value.update(studio_draft=current, capture_revision=current["revision"])
    for slot, image in current["images"].items():
        if current["product"].get("sku"):
            runtime.captura.stage_image(value, current["product"]["sku"], slot,
                                       value["studio_files"][image["id"]], current["revision"])


def clear(value):
    if active(value):
        with transaction() as db:
            put(db, root_for(value), value["email"], "capture_draft", {}, "disconnected")
    value.pop("studio_draft", None)
    value.pop("product_images", None)
    value["family_covers"] = {}


def recover_saved(value, current):
    """A previously started write is verified in Sheets, never repeated blindly."""
    from studio_api import runtime
    value.pop("capture_snapshot", None)
    _, sheet, rows = runtime.captura.snapshot(value)
    wanted = candidate(current["product"])
    row = next((r for r in rows if text(r.get("sku")) == wanted["sku"]), None)
    fields = ("nombre_producto", "Marca", "sku_padre", "codigo_barras", "atributo_nombre", "atributo_valor")
    if not row or any(text(row.get(k)) != text(wanted.get(k)) for k in fields if text(wanted.get(k))):
        raise ValueError("El guardado anterior quedó incierto y no se pudo verificar en Sheets. Revisa el inventario antes de iniciar otra captura; no se repitió la escritura.")
    current["saved"] = f"💾 {wanted['sku']} verificado en el inventario después de una interrupción.\nhttps://docs.google.com/spreadsheets/d/{sheet}/edit"
    current["save_phase"] = "saved"
    try:
        mirror(value, current)
    except Exception:
        pending(value, current)


def event_id(value, current):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, root_for(value) + ":" + value["email"] + ":" + current["revision"]))


def mirror_records(value, current, rows, images=None):
    """Atomic parent + child + mapping; replay never changes quantities again."""
    from .imports import normalize
    images = images or {}
    sku, parent_sku = current["product"]["sku"], current["product"].get("parent_sku", "")
    selected = [r for r in rows if text(r.get("sku")) in {sku, parent_sku}]
    selected = [dict(r) for r in selected]
    for row in selected:
        if text(row.get("sku")) == sku:
            p = current["product"]
            attributes = dict(p.get("attributes") or {})
            if p.get("size"):
                attributes.setdefault("Tamaño", p["size"])
            if p.get("variant") and not p.get("attribute_value"):
                attributes.setdefault("Variante", p["variant"])
            if p.get("product_type"):
                attributes.setdefault("Tipo reconocido", p["product_type"])
            row["attributes"] = attributes
    data, errors = normalize(selected)
    if errors or not any(r["sku"] == sku for r in data):
        raise ValueError("La captura está en Sheets pero no pudo validarse para el maestro. Revisa sus campos.")
    data.sort(key=lambda r: r["product_type"] != "variable")
    with transaction() as db:
        request_lock(db, root_for(value), "capture-save:" + sku.casefold())
        marker = db.get(SyncEvent, event_id(value, current))
        if marker and marker.status == "completed":
            return marker.product_id
        by_sku = {p.sku: p for p in db.scalars(select(Product).where(
            Product.tenant_id == root_for(value), Product.sku.in_([r["sku"] for r in data])))}
        if sku in by_sku:
            raise ValueError("El SKU ya está en el maestro. Revisa la ficha existente antes de reparar; no se sobrescribió.")
        for entry in data:
            entry = dict(entry)
            parent = entry.pop("parent_sku", "")
            filenames = entry.pop("images_legacy", "").split(",")
            if entry["product_type"] == "variable":
                entry["attributes"] = {k: [s.strip() for s in str(v).split(",") if s.strip()]
                                       for k, v in entry["attributes"].items()}
            if parent:
                if parent not in by_sku:
                    raise ValueError("No se encontró el padre. El padre y la variación no se guardaron parcialmente en el maestro.")
                entry["parent_id"] = by_sku[parent].id
            previous = by_sku.get(entry["sku"])
            if previous:
                # Existing parents retain all IDs and catalog fields; only their
                # variation options are updated by this capture.
                entry = {"product_type": "variable", "attributes": entry["attributes"]}
            product = save_product(db, root_for(value), value["email"], entry,
                                   previous.id if previous else None,
                                   previous.version if previous else None, source="capture",
                                   event_id=current["revision"])
            by_sku[product.sku] = product
            for filename in filenames:
                filename = filename.strip()
                key = images.get(filename)
                if not key:
                    continue
                existing = db.scalar(select(ProductImage.id).where(ProductImage.product_id == product.id,
                                                                      ProductImage.drive_file_id == key))
                if not existing:
                    role = "reference" if "_referencia_" in filename else "cover" if "_portada_" in filename else "gallery"
                    db.add(ProductImage(tenant_id=root_for(value), product_id=product.id, drive_file_id=key,
                                        role=role, status="approved", metadata_json={"canonical_filename": filename, "source": "capture"}))
        product = by_sku[sku]
        if not marker:
            marker = SyncEvent(id=event_id(value, current), tenant_id=root_for(value),
                               source="sheets", destination="catalog", action="capture.mirror")
            db.add(marker)
        marker.product_id, marker.status, marker.message = product.id, "completed", "Captura y relaciones incorporadas al catálogo."
        audit(db, root_for(value), value["email"], "capture.mirrored", product.id,
              after={"revision": current["revision"], "sku": sku})
        return product.id


def mirror(value, current):
    if not active(value):
        current["sync_status"] = "sheets_only"
        return
    from studio_api import runtime
    value.pop("capture_snapshot", None)
    service, _, rows = runtime.captura.snapshot(value)
    _, folder, _, _ = runtime._preparar_estructura(service, value)
    wanted = {current["product"]["sku"], current["product"].get("parent_sku", "")}
    image_ids = {}
    for row in rows:
        if text(row.get("sku")) in wanted:
            for filename in text(row.get("imagenes")).split(","):
                filename = filename.strip()
                if filename:
                    key = runtime._buscar_archivo(service, filename, folder)
                    if key:
                        image_ids[filename] = key
    current["master_product_id"] = mirror_records(value, current, rows, image_ids)
    current["sync_status"] = "synced"
    current.pop("sync_error", None)


def pending(value, current):
    current["sync_status"] = "pending_repair"
    current["sync_error"] = "El producto quedó guardado en Sheets. Falta incorporarlo al catálogo maestro; reparar no repetirá el guardado en Sheets."
    if active(value):
        try:
            with transaction() as db:
                marker = db.get(SyncEvent, event_id(value, current))
                if not marker:
                    marker = SyncEvent(id=event_id(value, current), tenant_id=root_for(value),
                                       source="sheets", destination="catalog", action="capture.mirror")
                    db.add(marker)
                marker.status, marker.message = "pending_repair", current["sync_error"]
        except Exception:
            # The pre-write checkpoint remains 'saving'. After a database
            # recovery that state forces a Sheet read before another attempt.
            pass
