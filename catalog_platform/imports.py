"""Explicit import preview/commit. Originals and operational catalog are backed up."""
# Importación revisada de CSV/XLSX/Sheets/WooCommerce, con respaldo y sin resucitar eliminados.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import csv
import io
import json
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from .models import Product, ProductImage, GenerationJob, uid
from .catalog import save_product, serialize, audit
from .database import transaction
from .security import seal
from . import queue


# Convierte filas externas al contrato de producto sin inventar cantidades ausentes.
def normalize(rows):
    from .api import ProductInput

    results = []
    errors = []
    seen = set()
    for index, row in enumerate(rows):
        try:
            sku = str(row.get("sku", "")).strip()
            if not sku:
                continue
            if sku in seen:
                raise ValueError("SKU duplicado en la fuente")
            seen.add(sku)
            kind = str(row.get("product_type", row.get("tipo", "simple"))).casefold()
            kind = {
                "variación": "variation",
                "variacion": "variation",
                "variante": "variation",
            }.get(kind, kind)
            if sku.upper().endswith("FULL"):
                kind = "variable"
            if kind == "variable" and row.get("sku_padre"):
                kind = "variation"
            category = str(
                row.get("category", row.get("categorias", row.get("categoria", "")))
            )
            parts = category.split(" > ", 1)
            tags = row.get("tags", row.get("etiquetas", []))
            if isinstance(tags, str):
                if tags.strip().startswith("["):
                    tags = json.loads(tags)
                else:
                    tags = [x.strip() for x in tags.split(",") if x.strip()]
            attrs = row.get("attributes", {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except ValueError:
                    attrs = {}
            if row.get("atributo_valor"):
                attrs[str(row.get("atributo_nombre") or "Tamaño")] = str(
                    row["atributo_valor"]
                )

            def number(key, legacy, default=0):
                val = row.get(key, row.get(legacy, default))
                return default if val in (None, "") else float(val)

            data = ProductInput(
                sku=sku,
                name=str(row.get("name", row.get("nombre_producto", ""))),
                brand=str(row.get("brand", row.get("Marca", row.get("marca", "")))),
                barcode=str(row.get("barcode", row.get("codigo_barras", ""))),
                category=parts[0],
                subcategory=(
                    parts[1]
                    if len(parts) > 1
                    else str(row.get("subcategory", row.get("subcategoria", "")))
                ),
                short_description=str(
                    row.get("short_description", row.get("descripcion_corta", ""))
                ),
                long_description=str(
                    row.get("long_description", row.get("descripcion_larga", ""))
                ),
                tags=tags,
                attributes=attrs,
                product_type=kind,
                price=None if kind == "variable" else number("price", "precio"),
                cost=number("cost", "costo", None),
                stock=None if kind == "variable" else number("stock", "Existencias"),
            )
            result = data.model_dump(exclude={"version"})
            result["parent_sku"] = str(
                row.get("parent_sku", row.get("sku_padre", ""))
            ).strip()
            result["images_legacy"] = str(row.get("imagenes", row.get("images", "")))[
                :1000
            ]
            results.append(result)
        except Exception:
            errors.append(
                {
                    "row": index + 2,
                    "sku": str(row.get("sku", ""))[:80],
                    "message": "Revisa SKU, tipo, nombre, cantidades o estructura de atributos.",
                }
            )
    return results, errors


# Valida CSV/XLSX recibido y extrae filas con límites de tamaño/estructura.
def parse_file(filename, raw):
    if len(raw) > 2_000_000:
        raise ValueError("El archivo supera 2 MB. Divide la importación.")
    if filename.lower().endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    elif filename.lower().endswith(".xlsx"):
        import openpyxl
        import zipfile

        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if (
                len(archive.infolist()) > 1000
                or sum(item.file_size for item in archive.infolist()) > 20000000
            ):
                raise ValueError("El Excel descomprimido supera el límite seguro.")
        book = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = (
            book["Lista completa"]
            if "Lista completa" in book.sheetnames
            else book.active
        )
        values = sheet.iter_rows(values_only=True)
        first = next(values, None)
        if first is None:
            raise ValueError("La hoja está vacía.")
        header = [str(v or "").strip() for v in first]
        rows = []
        for index, row in enumerate(values):
            if index >= 5000:
                raise ValueError("Máximo 5000 filas por importación.")
            rows.append(dict(zip(header, row)))
        book.close()
    else:
        raise ValueError("Usa CSV UTF-8 o Excel XLSX.")
    if len(rows) > 5000:
        raise ValueError("Máximo 5000 filas por importación.")
    return normalize(rows)


# Guarda un respaldo explícito antes de aplicar una importación autorizada.
def backup_catalog(db, tenant, drive):
    snapshot = {
        "created": datetime.now(timezone.utc).isoformat(),
        "products": [
            serialize(p)
            for p in db.scalars(select(Product).where(Product.tenant_id == tenant))
        ],
        "images": [
            serialize(p)
            for p in db.scalars(
                select(ProductImage).where(ProductImage.tenant_id == tenant)
            )
        ],
    }
    encrypted = seal(snapshot).encode()
    return drive.upload_bytes(
        encrypted,
        "catalogo_pre_import_" + uid() + ".json.enc",
        drive.working_folder("backups"),
        "application/octet-stream",
    )


# Procesa las filas confirmadas con checkpoints, identidad por tenant y auditoría.
def execute_import(job, value, drive, owner):
    payload = job["payload"]
    rows = payload["rows"]
    drive_index = {}
    if any(row.get("images_legacy") for row in rows):
        from studio_api import runtime

        _, folder, _, _ = runtime._preparar_estructura(drive, value)
        if folder:
            drive_index = {
                f["name"].casefold(): f
                for f in drive.list(folder, fields="id,name,mimeType")
            }
    for index, data in enumerate(
        sorted(rows, key=lambda r: 0 if r["product_type"] == "variable" else 1)
    ):
        queue.checkpoint(job["id"], owner)
        if str(index) in payload.get("completed_keys", []):
            continue
        with transaction() as db:
            existing = db.scalar(
                select(Product).where(
                    Product.tenant_id == job["tenant_id"], Product.sku == data["sku"]
                )
            )
            imported = payload.get("imported_products", {})
            pid = imported.get(data["sku"])
            if not existing:
                fields = {
                    k: v
                    for k, v in data.items()
                    if k not in {"parent_sku", "images_legacy"}
                }
                if data["product_type"] == "variation":
                    parent = db.scalar(
                        select(Product).where(
                            Product.tenant_id == job["tenant_id"],
                            Product.sku == data["parent_sku"],
                            Product.product_type == "variable",
                        )
                    )
                    if not parent:
                        raise ValueError(
                            "Falta el padre de "
                            + data["sku"]
                            + ". Importa primero la familia completa."
                        )
                    fields["parent_id"] = parent.id
                p = save_product(
                    db,
                    job["tenant_id"],
                    job["actor"],
                    fields,
                    source="import",
                    event_id=job["id"] + ":" + data["sku"],
                )
                pid = p.id
                imported = {**imported, data["sku"]: pid}
                audit(
                    db,
                    job["tenant_id"],
                    job["actor"],
                    "product.imported",
                    pid,
                    after={"source_checksum": payload["checksum"], "job_id": job["id"]},
                )
                saved = db.get(GenerationJob, job["id"])
                saved.payload = {**saved.payload, "imported_products": imported}
                payload = saved.payload
        if pid and data.get("images_legacy"):
            attach_historic_images(job, data, pid, drive_index, drive, owner)
        with transaction() as db:
            saved = db.get(GenerationJob, job["id"])
            completed = list(saved.payload.get("completed_keys", [])) + [str(index)]
            saved.payload = {**saved.payload, "completed_keys": completed}
            saved.progress = int((index + 1) * 100 / len(rows))
            payload = saved.payload
        queue.checkpoint(
            job["id"],
            owner,
            message=f"Importando {index+1}/{len(rows)}; conserva productos existentes",
        )
    return True


# Asocia imágenes existentes por el naming aceptado; no reorganiza originales en Drive.
def attach_historic_images(job, data, product_id, drive_index, drive, owner):
    from woocommerce_image_sync import resolve_product_images
    from PIL import Image
    from .models import SyncEvent

    refs = resolve_product_images(
        {"sku": data["sku"], "imagenes": data["images_legacy"]}, drive_index
    )
    for ref in refs:
        file = ref["drive_file"]
        if not file:
            with transaction() as db:
                db.add(
                    SyncEvent(
                        tenant_id=job["tenant_id"],
                        product_id=product_id,
                        source="drive",
                        destination="app",
                        action="Imagen histórica",
                        status="pending",
                        message="No se encontró " + ref["requested_filename"],
                        job_id=job["id"],
                    )
                )
            continue
        with transaction() as db:
            if db.scalar(
                select(ProductImage.id).where(
                    ProductImage.tenant_id == job["tenant_id"],
                    ProductImage.product_id == product_id,
                    ProductImage.drive_file_id == file["id"],
                )
            ):
                continue
        queue.checkpoint(
            job["id"], owner, message="Validando imagen histórica " + file["name"]
        )
        raw = drive.download(file["id"])
        with Image.open(io.BytesIO(raw)) as picture:
            picture.verify()
            width, height = picture.size
        if width * height > 24000000:
            raise ValueError("Imagen histórica demasiado grande.")
        with transaction() as db:
            db.add(
                ProductImage(
                    tenant_id=job["tenant_id"],
                    product_id=product_id,
                    drive_file_id=file["id"],
                    role={0: "main", 1: "lifestyle", 2: "commercial"}.get(
                        ref["position"], "gallery"
                    ),
                    status="approved",
                    checksum=hashlib.sha256(raw).hexdigest(),
                    width=width,
                    height=height,
                    mime_type=file.get("mimeType", "image/jpeg"),
                    metadata_json={
                        "origin": "historic_import",
                        "filename": file["name"],
                        "source_name": ref["requested_filename"],
                        "previous_workflow_approved": True,
                    },
                )
            )
            audit(
                db,
                job["tenant_id"],
                job["actor"],
                "historic_image.linked",
                product_id,
                after={"file_id": file["id"], "filename": file["name"]},
            )
