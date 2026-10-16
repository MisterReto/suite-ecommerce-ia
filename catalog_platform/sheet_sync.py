"""Explicit Sheets/catalog reconciliation and recoverable product removal."""

import hashlib
import json
import os

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

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


def named_images(drive, names, *, warnings=None):
    """Read exact names only from direct children of imagenes_generadas."""
    names = {name for name in names if name and "/" not in name and "\\" not in name}
    if not names:
        return {}
    folder = drive.generated_images_folder()
    results = {}
    duplicates = set()
    items = drive.list(folder, "mimeType contains 'image/'",
                       fields="id,name,mimeType,parents,trashed", limit=20000) if folder else []
    for item in items:
        name = item.get("name")
        if (name not in names or folder not in item.get("parents", []) or item.get("trashed")
                or not item.get("mimeType", "").startswith("image/")):
            continue
        if name in results and results[name] != item["id"]:
            if warnings is None:
                raise ValueError(f"Hay imágenes duplicadas con el mismo nombre en imagenes_generadas: {name}. Revisa esa carpeta antes de continuar.")
            duplicates.add(name)
        results[name] = item["id"]
    for name in duplicates:
        results.pop(name, None)
    if warnings is not None:
        for name in sorted(names - results.keys()):
            reason = "Hay varias imágenes con este nombre" if name in duplicates else "No se encontró la imagen"
            warnings.append({"image": name, "message": f"{reason} en imagenes_generadas. Se omitió esta imagen; los datos del producto sí se pueden sincronizar."})
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
    normalized, errors = normalize(selected, detailed_errors=True)
    if errors or len(normalized) != len(selected):
        raise ValueError(errors[0]["message"] if errors else "Los datos de Sheets no pudieron validarse para el catálogo de la app.")
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
    """Re-read under the capture lock, isolating each product with a savepoint."""
    if not configured():
        raise ValueError("Conecta la base de datos del catálogo antes de sincronizar.")
    require_role(value, "admin", "editor")
    if not isinstance(skus, list) or not 1 <= len(skus) <= 500 or any(not isinstance(sku, str) for sku in skus):
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
        requested = {sku.strip() for sku in skus}
        wanted = requested.copy()
        for sku in requested:
            matches = by_sku.get(sku, [])
            if len(matches) == 1 and text(matches[0].get("sku_padre")):
                wanted.add(text(matches[0]["sku_padre"]))
        warnings, failed, selected, normalized = [], set(), {}, {}

        def warn(sku, message, *, failure=False, image=None):
            matches = by_sku.get(sku, [])
            item = {"sku": sku, "name": text(matches[0].get("nombre_producto")) if len(matches) == 1 else "", "message": message}
            if image:
                item["image"] = image
            warnings.append(item)
            if failure:
                failed.add(sku)

        for sku in sorted(wanted):
            if not sku or len(sku) > 80:
                warn(sku, "El SKU debe contener entre 1 y 80 caracteres.", failure=True)
                continue
            matches = by_sku.get(sku, [])
            if len(matches) != 1:
                reason = "El SKU está duplicado en Sheets" if matches else "El SKU falta en Sheets"
                warn(sku, reason + ". Corrige el inventario y vuelve a sincronizarlo.", failure=True)
                continue
            data, errors = normalize(matches, detailed_errors=True)
            if errors or not data:
                warn(sku, errors[0]["message"] if errors else "Faltan datos del producto.", failure=True)
                continue
            selected[sku], normalized[sku] = matches[0], data[0]

        image_warnings = []
        try:
            files = named_images(drive, set().union(*(image_names(row) for row in selected.values())), warnings=image_warnings)
        except Exception:
            # A Drive image lookup outage need not prevent saving product data.
            files = {}
            image_warnings = [{"image": name, "message": "No se pudieron consultar las imágenes en Drive. Revisa la conexión y los permisos; se sincronizaron los datos sin añadir esta imagen."}
                              for name in sorted(set().union(*(image_names(row) for row in selected.values())))]
        saved = {}
        for sku in sorted(selected, key=lambda key: (normalized[key]["product_type"] == "variation", key)):
            data = normalized[sku]
            parent = data["parent_sku"]
            if data["product_type"] == "variation" and (parent not in saved or normalized[parent]["product_type"] != "variable"):
                warn(sku, f"No se pudo sincronizar su padre {parent or '(sin SKU padre)'}. Revisa que exista una sola fila de tipo variable y corrige sus advertencias.", failure=True)
                continue
            try:
                # Roll back this product's fields, images, stock and audit together.
                with db.begin_nested():
                    product_ids = mirror_rows(db, value, root, [selected[sku]], files, fresh=True)
                    db.flush()
                saved.update(product_ids)
            except (ValueError, HTTPException) as exc:
                from app_security import public_error
                warn(sku, public_error(ValueError(exc.detail) if isinstance(exc, HTTPException) else exc), failure=True)
                continue
            except SQLAlchemyError:
                warn(sku, "No se pudo guardar el producto en la base de datos. Revisa conflictos de SKU y sus relaciones antes de reintentar.", failure=True)
                continue
            except Exception:
                warn(sku, "Un error interno impidió guardar este producto. Revisa los registros del servidor y vuelve a sincronizarlo.", failure=True)
                continue
            for issue in image_warnings:
                if issue["image"] in image_names(selected[sku]):
                    warn(sku, issue["message"], image=issue["image"])
    value.pop("capture_snapshot", None)
    return {"requested": len(requested), "updated": len(saved), "failed": len(failed),
            "product_ids": list(saved.values()), "warnings": warnings}


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
