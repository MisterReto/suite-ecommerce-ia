"""Worker-side reads: real orders, ID mappings and identified stock snapshots."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .database import transaction
from .models import (
    Product,
    ProductImage,
    OrderSnapshot,
    IntegrationMapping,
    SyncEvent,
    now,
)
from .catalog import serialize, save_product, move_stock, audit
from . import queue


def parse_time(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (
            stamp.replace(tzinfo=timezone.utc)
            if stamp.tzinfo is None
            else stamp.astimezone(timezone.utc)
        )
    except ValueError:
        return None


def store_order(db, tenant, data):
    stamp = parse_time(data.get("date_created_gmt"))
    if not stamp or not data.get("id"):
        return
    order = db.scalar(
        select(OrderSnapshot).where(
            OrderSnapshot.tenant_id == tenant,
            OrderSnapshot.woocommerce_id == int(data["id"]),
        )
    )
    if not order:
        order = OrderSnapshot(tenant_id=tenant, woocommerce_id=int(data["id"]))
        db.add(order)
    order.status = str(data.get("status", "unknown"))[:40]
    order.total = float(data.get("total", 0))
    order.currency = str(data.get("currency", "MXN"))[:10]
    order.ordered_at = stamp


def apply_snapshot(db, product, data, event_id, actor):
    if product.status == "deleted":
        return False
    if str(data.get("sku", "")) != product.sku:
        raise ValueError("El ID de WooCommerce ya no coincide con el SKU.")
    modified = parse_time(data.get("date_modified_gmt"))
    previous = product.woocommerce_updated_at
    if previous and modified and modified < parse_time(previous):
        return False
    quantity = data.get("stock_quantity")
    if quantity is not None and product.product_type != "variable":
        quantity = float(quantity)
        if not 0 <= quantity <= 1000000:
            raise ValueError("Cantidad remota inválida.")
        product.woocommerce_stock = quantity
        if os.getenv("STOCK_AUTHORITY", "app") == "woocommerce" and modified:
            move_stock(
                db,
                product,
                quantity,
                "woocommerce",
                event_id,
                actor,
                {"remote_modified_at": modified.isoformat()},
            )
    product.woocommerce_updated_at = modified or previous
    product.last_woocommerce_sync = now()
    product.sync_status = (
        "synced"
        if product.stock == product.woocommerce_stock
        or product.product_type == "variable"
        else "difference"
    )
    return True


def refresh(job, owner, value=None, drive=None):
    from ecommerce_services import WooCommerceService, WordPressMediaService

    woo = WooCommerceService()
    start = (
        datetime.now(ZoneInfo("America/Mexico_City"))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
    )
    after = (start - timedelta(days=1)).replace(tzinfo=None).isoformat()
    for page in range(1, 11):
        queue.checkpoint(job["id"], owner, message=f"Consultando pedidos, página {page}")
        orders = woo.orders(after, page)
        with transaction() as db:
            for data in orders:
                store_order(db, job["tenant_id"], data)
        if len(orders) < 100:
            break
    else:
        raise ValueError(
            "Hay más de 1000 pedidos recientes; divide el intervalo de lectura."
        )
    if job["payload"].get("import_products"):
        from .imports import backup_catalog

        queue.checkpoint(job["id"], owner, message="Preparando lectura del catálogo WooCommerce")
        with transaction() as db:
            backup_catalog(db, job["tenant_id"], drive)
        rows = woo.client.list_all_products()
        if len(rows) > 3000:
            raise ValueError(
                "El catálogo remoto supera 3000 productos; divide la importación."
            )
        parents = []
        for index, data in enumerate(rows):
            queue.checkpoint(job["id"], owner)
            if not data.get("sku"):
                continue
            with transaction() as db:
                if db.scalar(select(Product.id).where(
                    Product.tenant_id == job["tenant_id"], Product.status == "deleted",
                    Product.woocommerce_product_id == int(data["id"]),
                    Product.woocommerce_variation_id.is_(None),
                ).limit(1)):
                    continue  # An ordinary refresh must not resurrect a removed record.
                existing = db.scalar(
                    select(Product).where(
                        Product.tenant_id == job["tenant_id"],
                        Product.sku == str(data["sku"]),
                    )
                )
                known = serialize(existing) if existing else None
                if known and (
                    known["woocommerce_product_id"] != int(data["id"])
                    or known["woocommerce_variation_id"]
                ):
                    continue
            full = woo.product(int(data["id"]))
            if full.get("type") not in {"simple", "variable"}:
                continue
            fields = remote_fields(full)
            with transaction() as db:
                if known:
                    stored = db.scalar(select(Product).where(Product.id == known["id"]).with_for_update())
                    if stored.status == "deleted":
                        continue
                p = (
                    stored
                    if known
                    else save_product(
                        db,
                        job["tenant_id"],
                        job["actor"],
                        fields,
                        source="woocommerce-import",
                        event_id=job["id"] + ":" + str(full["id"]),
                    )
                )
                p.woocommerce_product_id = int(full["id"])
                p.status = "published" if full.get("status") == "publish" else "pending"
                p.wordpress_media_ids = [
                    int(i["id"]) for i in full.get("images", []) if i.get("id")
                ]
                if not known:
                    db.add(
                        IntegrationMapping(
                            tenant_id=job["tenant_id"],
                            internal_product_id=p.id,
                            provider="woocommerce",
                            entity_type="product",
                            external_id=str(full["id"]),
                        )
                    )
                pid = p.id
            if full.get("type") == "variable":
                parents.append((pid, full))
            copy_first_image(job, value, drive, pid, full)
            queue.checkpoint(
                job["id"],
                owner,
                progress=int((index + 1) * 80 / max(len(rows), 1)),
                message=f"Importando WooCommerce {index+1}/{len(rows)}",
            )
        for parent_id, parent in parents:
            for item in woo.client.list_all_variations(int(parent["id"])):
                queue.checkpoint(job["id"], owner)
                if not item.get("sku"):
                    continue
                with transaction() as db:
                    if db.scalar(select(Product.id).where(
                        Product.tenant_id == job["tenant_id"], Product.status == "deleted",
                        Product.woocommerce_product_id == int(parent["id"]),
                        Product.woocommerce_variation_id == int(item["id"]),
                    ).limit(1)):
                        continue
                    existing = db.scalar(
                        select(Product).where(
                            Product.tenant_id == job["tenant_id"],
                            Product.sku == str(item["sku"]),
                        )
                    )
                    if existing:
                        if existing.woocommerce_variation_id == int(
                            item["id"]
                        ) and existing.woocommerce_product_id == int(parent["id"]):
                            copy_first_image(
                                job,
                                value,
                                drive,
                                existing.id,
                                {
                                    **item,
                                    "images": (
                                        [item["image"]] if item.get("image") else []
                                    ),
                                },
                            )
                        continue
                    fields = remote_fields(item)
                    fields.update(
                        product_type="variation",
                        parent_id=parent_id,
                        name=item.get("name") or parent["name"],
                    )
                    p = save_product(
                        db,
                        job["tenant_id"],
                        job["actor"],
                        fields,
                        source="woocommerce-import",
                        event_id=job["id"] + ":" + str(item["id"]),
                    )
                    p.woocommerce_product_id = int(parent["id"])
                    p.woocommerce_variation_id = int(item["id"])
                    p.status = (
                        "published" if item.get("status") == "publish" else "pending"
                    )
                    if item.get("image"):
                        p.wordpress_media_ids = [int(item["image"]["id"])]
                    db.add(
                        IntegrationMapping(
                            tenant_id=job["tenant_id"],
                            internal_product_id=p.id,
                            provider="woocommerce",
                            entity_type="variation",
                            external_id=str(item["id"]),
                            parent_external_id=str(parent["id"]),
                        )
                    )
                    pid = p.id
                copy_first_image(
                    job,
                    value,
                    drive,
                    pid,
                    {**item, "images": [item["image"]] if item.get("image") else []},
                )
    with transaction() as db:
        products = db.scalars(
            select(Product).where(
                Product.tenant_id == job["tenant_id"],
                Product.status != "deleted",
                Product.woocommerce_product_id.is_not(None),
            )
        ).all()
    for index, p in enumerate(products):
        queue.checkpoint(job["id"], owner)
        data = woo.resolve(p)
        event_id = (
            "pull:"
            + hashlib.sha256(
                json.dumps(
                    {
                        "id": data.get("id"),
                        "modified": data.get("date_modified_gmt"),
                        "stock": data.get("stock_quantity"),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        )
        with transaction() as db:
            stored = db.get(Product, p.id)
            apply_snapshot(db, stored, data, event_id, job["actor"])
            db.add(
                SyncEvent(
                    tenant_id=job["tenant_id"],
                    product_id=p.id,
                    source="woocommerce",
                    destination="app",
                    action="Lectura de stock",
                    status="completed",
                    message="Mapping consultado por ID",
                )
            )
        queue.checkpoint(
            job["id"],
            owner,
            progress=80 + int((index + 1) * 19 / max(len(products), 1)),
            message=f"Verificando stock {index+1}/{len(products)}",
        )
    return True


def remote_fields(data):
    return {
        "sku": str(data["sku"]),
        "name": str(data.get("name", data["sku"]))[:180],
        "barcode": "",
        "brand": (
            str(data.get("brands", [{}])[0].get("name", ""))[:120]
            if data.get("brands")
            else ""
        ),
        "category": (
            data.get("categories", [{}])[0].get("name", "")
            if data.get("categories")
            else ""
        ),
        "subcategory": "",
        "short_description": str(data.get("short_description", "")),
        "long_description": str(data.get("description", "")),
        "tags": [t["name"] for t in data.get("tags", [])],
        "attributes": {
            a["name"]: a.get("options", a.get("option", ""))
            for a in data.get("attributes", [])
        },
        "product_type": data.get("type", "simple"),
        "price": (
            None
            if data.get("type") == "variable"
            else float(data.get("regular_price") or data.get("price") or 0)
        ),
        "cost": None,
        "stock": (
            None
            if data.get("type") == "variable"
            else float(data.get("stock_quantity") or 0)
        ),
    }


def copy_first_image(job, value, drive, product_id, data):
    images = data.get("images", [])
    if not images:
        return
    with transaction() as db:
        if db.scalar(
            select(ProductImage.id)
            .where(
                ProductImage.tenant_id == job["tenant_id"],
                ProductImage.product_id == product_id,
                ProductImage.role != "reference",
            )
            .limit(1)
        ):
            return
    from ecommerce_services import WordPressMediaService
    from PIL import Image, ImageOps
    import io

    raw = WordPressMediaService().download(int(images[0]["id"]))
    with Image.open(io.BytesIO(raw)) as source:
        picture = ImageOps.exif_transpose(source).convert("RGB")
        picture.thumbnail((2400, 2400))
        path = f"/tmp/{value['file_namespace']}_import_{product_id}.jpg"
        picture.save(path, "JPEG", quality=92)
    file = drive.upload(
        path,
        f"{data['sku']}_import_wc_{images[0]['id']}.jpg",
        drive.working_folder("images", "originals"),
    )
    checksum = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with transaction() as db:
        db.add(
            ProductImage(
                tenant_id=job["tenant_id"],
                product_id=product_id,
                drive_file_id=file["id"],
                role="main",
                status="published",
                checksum=checksum,
                width=picture.width,
                height=picture.height,
                metadata_json={
                    "wordpress_media_id": int(images[0]["id"]),
                    "origin": "woocommerce_import",
                },
            )
        )
