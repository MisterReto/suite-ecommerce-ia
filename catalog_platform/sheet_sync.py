"""Explicit Sheets/catalog reconciliation and recoverable product removal."""

import hashlib
import json
import os

from sqlalchemy import select

from catalog_capture import text
from catalog_taxonomy import read_inventory
from drive_service import DriveService
from sheets_service import SheetsService
from .catalog import save_product, audit
from .database import configured, transaction
from .imports import normalize
from .models import Product, ProductImage, GeneratedAsset, AuditLog, uid
from .queue import request_lock
from .security import require_role


def named_images(drive, names):
    """Resolve exact filenames inside the selected root, never by SKU prefix."""
    results = {}
    for name in sorted(set(names)):
        if not name or "/" in name or "\\" in name:
            continue
        escaped = name.replace("'", "\\'")
        page = None
        matches = []
        while True:
            response = drive.files().list(
                q=f"name = '{escaped}' and trashed = false and mimeType contains 'image/'",
                fields="nextPageToken,files(id,name,mimeType)", pageSize=100, pageToken=page,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            matches.extend(file for file in response.get("files", []) if drive.owns(file["id"]))
            page = response.get("nextPageToken")
            if not page:
                break
        if len(matches) > 1:
            raise ValueError("Hay imágenes duplicadas con el mismo nombre. Revisa los archivos antes de continuar.")
        if matches:
            results[name] = matches[0]["id"]
    return results


def image_names(row):
    return {name.strip() for name in text(row.get("imagenes")).split(",") if name.strip()}


def sync_inventory_product(value, row, inventory):
    """Mirror a successfully synchronized table row into the app's own catalog."""
    if not configured():
        return None
    require_role(value, "admin", "editor")
    root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root:
        raise ValueError("Selecciona la carpeta del catálogo antes de sincronizar.")
    selected = [row]
    parent_sku = text(row.get("sku_padre"))
    if parent_sku:
        parents = [item for item in inventory if text(item.get("sku")) == parent_sku]
        if len(parents) != 1:
            raise ValueError("La variación requiere un padre único en Sheets.")
        selected = parents + selected
    from studio_api import runtime
    drive = DriveService(runtime._get_drive_service(value), root)
    files = named_images(drive, set().union(*(image_names(item) for item in selected)))
    with transaction() as db:
        request_lock(db, root, "capture-sheet-writer")
        result = mirror_rows(db, value, root, selected, files)[text(row.get("sku"))]
    value.pop("capture_snapshot", None)
    return result


def mirror_rows(db, value, root, selected, files, *, fresh=False):
    """Upsert a validated family in one transaction, retaining existing identities."""
    normalized, errors = normalize(selected)
    if errors or len(normalized) != len(selected):
        raise ValueError("Los datos de Sheets no pudieron validarse para el catálogo de la app.")
    from studio_api import runtime
    saved = {}
    for data in sorted(normalized, key=lambda item: item["product_type"] != "variable"):
        fields = {key: item for key, item in data.items() if key not in {"parent_sku", "images_legacy"}}
        existing = db.scalar(select(Product).where(Product.tenant_id == root, Product.sku == data["sku"]).with_for_update())
        deleted = db.scalar(select(AuditLog.id).where(
            AuditLog.tenant_id == root, AuditLog.action == "product.deleted",
            AuditLog.before["sku"].as_string() == data["sku"],
        ).limit(1)) if not existing and not fresh else None
        if deleted and not any(text(item.get("sku")) == data["sku"] for item in read_inventory(runtime, value)[2]):
            raise ValueError("El SKU ya fue eliminado de Sheets. Recarga la tabla antes de sincronizar.")
        if data["product_type"] == "variation":
            parent = saved.get(data["parent_sku"]) or db.scalar(select(Product).where(
                Product.tenant_id == root, Product.sku == data["parent_sku"], Product.status != "deleted"))
            if not parent:
                raise ValueError("Falta el padre en el catálogo.")
            fields["parent_id"] = parent.id
        checksum = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        product = save_product(db, root, value["email"], fields,
                               existing.id if existing else None, existing.version if existing else None,
                               source="sheets", event_id="table-sync:" + uid())
        saved[product.sku] = product
        for name in data["images_legacy"].split(","):
            file_id = files.get(name.strip())
            if file_id and not db.scalar(select(ProductImage.id).where(
                ProductImage.tenant_id == root, ProductImage.product_id == product.id, ProductImage.drive_file_id == file_id)):
                db.add(ProductImage(tenant_id=root, product_id=product.id, drive_file_id=file_id,
                                    role="gallery", status="approved", metadata_json={"canonical_filename": name.strip(), "source": "sheets"}))
        audit(db, root, value["email"], "sheets.table_synced", product.id, after={"sku": product.sku, "source_checksum": checksum})
    return {sku: product.id for sku, product in saved.items()}


def sync_inventory(value, skus):
    """Re-read selected SKUs under the same lock as capture and Drive deletion."""
    if not configured():
        raise ValueError("Conecta la base de datos del catálogo antes de sincronizar.")
    require_role(value, "admin", "editor")
    if not isinstance(skus, list) or not 1 <= len(skus) <= 500 or any(not isinstance(sku, str) or not sku.strip() or len(sku) > 80 for sku in skus):
        raise ValueError("Selecciona entre 1 y 500 SKU válidos.")
    root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root:
        raise ValueError("Selecciona la carpeta del catálogo antes de sincronizar.")
    from studio_api import runtime
    with transaction() as db:
        request_lock(db, root, "capture-sheet-writer")
        client, sheet, rows = read_inventory(runtime, value)
        drive = DriveService(client, root)
        if not sheet or not drive.owns(sheet):
            raise ValueError("No se encontró el inventario dentro de la carpeta autorizada.")
        by_sku = {}
        for row in rows:
            by_sku.setdefault(text(row.get("sku")), []).append(row)
        wanted = {sku.strip() for sku in skus}
        for sku in list(wanted):
            matches = by_sku.get(sku, [])
            if len(matches) != 1:
                raise ValueError("Un SKU falta o está duplicado en Sheets. Recarga la tabla.")
            parent = text(matches[0].get("sku_padre"))
            if parent:
                wanted.add(parent)
        if any(len(by_sku.get(sku, [])) != 1 for sku in wanted):
            raise ValueError("La variación requiere un padre único en Sheets.")
        selected = [by_sku[sku][0] for sku in sorted(wanted)]
        files = named_images(drive, set().union(*(image_names(item) for item in selected)))
        saved = mirror_rows(db, value, root, selected, files, fresh=True)
    value.pop("capture_snapshot", None)
    return {"updated": len(saved), "product_ids": list(saved.values())}


def delete_from_drive(db, value, product):
    """Back up sources, trash unshared images and remove the verified Sheet row."""
    from studio_api import runtime
    client, spreadsheet_id, rows = read_inventory(runtime, value)
    if not spreadsheet_id:
        raise ValueError("No se encontró inventario_completo en la carpeta autorizada.")
    drive = DriveService(client, product.tenant_id)
    if not drive.owns(spreadsheet_id):
        raise ValueError("La hoja está fuera del catálogo autorizado.")
    matches = [row for row in rows if text(row.get("sku")).casefold() == product.sku.casefold()]
    if len(matches) > 1:
        raise ValueError("El SKU está duplicado en Sheets.")
    row = matches[0] if matches else {}
    others = [item for item in rows if text(item.get("sku")).casefold() != product.sku.casefold()]
    shared_names = set().union(*(image_names(item) for item in others)) if others else set()
    files = set(named_images(drive, image_names(row) - shared_names).values())
    files.update(db.scalars(select(ProductImage.drive_file_id).where(
        ProductImage.tenant_id == product.tenant_id, ProductImage.product_id == product.id)))
    files.update(db.scalars(select(GeneratedAsset.raw_drive_file_id).where(
        GeneratedAsset.tenant_id == product.tenant_id, GeneratedAsset.product_id == product.id)))
    shared = set(db.scalars(select(ProductImage.drive_file_id).join(Product, Product.id == ProductImage.product_id).where(
        ProductImage.tenant_id == product.tenant_id, Product.id != product.id, Product.status != "deleted")))
    shared.update(db.scalars(select(GeneratedAsset.raw_drive_file_id).join(Product, Product.id == GeneratedAsset.product_id).where(
        GeneratedAsset.tenant_id == product.tenant_id, Product.id != product.id, Product.status != "deleted")))
    planned = []
    for file_id in sorted(files - shared - {""}):
        if not drive.owns(file_id, include_trashed=True):
            raise ValueError("Una imagen está fuera de la carpeta autorizada.")
        info = drive.files().get(fileId=file_id, supportsAllDrives=True, fields="id,name,mimeType,trashed").execute()
        if info.get("name") in shared_names:
            continue
        if not str(info.get("mimeType", "")).startswith("image/"):
            raise ValueError("Un archivo asociado no es una imagen.")
        planned.append(info)
    backup = drive.backup(spreadsheet_id, "inventario_antes_eliminar_" + product.id)
    image_backups = []
    for info in planned:
        if not info.get("trashed"):
            image_backups.append(drive.backup(info["id"], "imagen_antes_eliminar_" + product.id + "_" + info["id"]))
        drive.trash_image(info["id"])
    sheets = SheetsService(runtime._get_sheets_service(value), spreadsheet_id)
    deleted = sheets.delete_sku(product.sku)
    return {"sheet": deleted, "backup_id": backup["id"], "trashed_image_ids": [info["id"] for info in planned],
            "image_backup_ids": [item["id"] for item in image_backups]}
