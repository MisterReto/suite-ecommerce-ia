"""Catalog operations: optimistic edits, identified stock movements, stable IDs."""

import csv
import io
import json
import os
from sqlalchemy import select
from fastapi import HTTPException
from app_security import clean_html
from .models import (
    Product,
    ProductImage,
    ProductVariant,
    Category,
    Brand,
    InventoryMovement,
    AuditLog,
    SyncEvent,
    GenerationJob,
    uid,
)

FIELDS = (
    "sku",
    "barcode",
    "name",
    "brand",
    "category",
    "subcategory",
    "short_description",
    "long_description",
    "tags",
    "attributes",
    "product_type",
    "parent_id",
    "price",
    "cost",
    "stock",
)


def serialize(record):
    result = {
        column.name: getattr(record, column.name) for column in record.__table__.columns
    }
    for key, value in list(result.items()):
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    return result


def product_for(db, tenant, product_id, lock=False):
    query = select(Product).where(Product.tenant_id == tenant, Product.id == product_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    product = db.scalar(query)
    if not product:
        raise HTTPException(404, "Producto no disponible.")
    return product


def audit(
    db,
    tenant,
    actor,
    action,
    product_id=None,
    before=None,
    after=None,
    result="completed",
    system="app",
):
    db.add(
        AuditLog(
            tenant_id=tenant,
            actor=actor,
            action=action,
            product_id=product_id,
            before=before or {},
            after=after or {},
            result=result,
            system=system,
        )
    )


def move_stock(
    db, product, quantity, source, event_id, actor, metadata=None, store_id=""
):
    if product.product_type == "variable":
        raise ValueError("Las portadas FULL no tienen existencias propias.")
    previous = db.scalar(
        select(InventoryMovement).where(
            InventoryMovement.tenant_id == product.tenant_id,
            InventoryMovement.product_id == product.id,
            InventoryMovement.source == source,
            InventoryMovement.source_event_id == event_id,
        )
    )
    if previous:
        return previous
    before = product.stock
    product.stock = quantity
    product.version += 1
    movement = InventoryMovement(
        tenant_id=product.tenant_id,
        product_id=product.id,
        variant_id=product.id if product.parent_id else None,
        source=source,
        source_event_id=event_id,
        store_id=store_id,
        quantity_before=before,
        quantity_after=quantity,
        delta=quantity - (before or 0),
        metadata_json=metadata or {},
    )
    db.add(movement)
    audit(
        db,
        product.tenant_id,
        actor,
        "stock.changed",
        product.id,
        {"stock": before},
        {"stock": quantity, "source": source, "event_id": event_id},
    )
    return movement


def save_product(
    db,
    tenant,
    actor,
    data,
    product_id=None,
    expected_version=None,
    source="app",
    event_id=None,
):
    product = (
        product_for(db, tenant, product_id, lock=True)
        if product_id
        else Product(tenant_id=tenant, id=uid())
    )
    if product_id and expected_version != product.version:
        raise HTTPException(409, "El producto cambió. Recarga antes de guardar.")
    if (
        product_id
        and source == "app"
        and db.scalar(
            select(GenerationJob.id).where(
                GenerationJob.product_id == product.id,
                GenerationJob.tenant_id == tenant,
                GenerationJob.kind.in_(["publication", "stock_sync"]),
                GenerationJob.status.in_(["queued", "processing"]),
            )
        )
    ):
        raise HTTPException(
            409,
            "El producto tiene una escritura a la tienda en curso. Espera su resultado antes de editar.",
        )
    before = (
        {field: getattr(product, field, None) for field in FIELDS} if product_id else {}
    )
    if (
        product_id
        and product.product_type == "variation"
        and data.get("product_type") != "variation"
    ):
        raise ValueError(
            "Una variación existente debe conservar su familia; crea una ficha nueva para cambiar su tipo."
        )
    if (
        product_id
        and product.product_type == "variable"
        and data.get("product_type") != "variable"
        and db.scalar(
            select(Product.id).where(Product.parent_id == product.id).limit(1)
        )
    ):
        raise ValueError(
            "Este padre tiene variaciones. Conserva su tipo para proteger la familia."
        )
    if (
        source == "app"
        and os.getenv("STOCK_AUTHORITY", "app") == "loyverse"
        and data.get("stock") is not None
        and data["stock"] != product.stock
    ):
        raise ValueError(
            "Loyverse es la autoridad de stock; registra el cambio en POS."
        )
    if data.get("parent_id"):
        parent = product_for(db, tenant, data["parent_id"])
        if parent.product_type != "variable" or parent.id == product.id:
            raise ValueError("La variación requiere un padre variable válido.")
    if data.get("product_type") == "variation" and not data.get("parent_id"):
        raise ValueError("Selecciona el padre de la variación.")
    for field in FIELDS:
        if field == "stock":
            continue
        if field in data:
            setattr(product, field, data[field])
    product.short_description = clean_html(product.short_description or "")
    product.long_description = clean_html(product.long_description or "")
    if product.product_type == "variable":
        product.price = None
        product.cost = None
        product.stock = None
        product.parent_id = None
    if product.product_type == "simple":
        product.parent_id = None
    if not product_id:
        db.add(product)
        db.flush()
    if (
        data.get("stock") is not None
        and product.product_type != "variable"
        and (not product_id or float(data["stock"]) != product.stock)
    ):
        move_stock(db, product, float(data["stock"]), source, event_id or uid(), actor)
    if product_id:
        product.version += 1
    product.sync_status = "pending"
    for kind, name in ((Category, product.category), (Brand, product.brand)):
        if name and not db.scalar(
            select(kind.id).where(kind.tenant_id == tenant, kind.name == name)
        ):
            db.add(kind(tenant_id=tenant, name=name))
    if product.product_type == "variation":
        variant = db.scalar(
            select(ProductVariant).where(
                ProductVariant.tenant_id == tenant,
                ProductVariant.child_product_id == product.id,
            )
        )
        if variant:
            variant.product_id = product.parent_id
            variant.attributes = product.attributes
        else:
            db.add(
                ProductVariant(
                    tenant_id=tenant,
                    product_id=product.parent_id,
                    child_product_id=product.id,
                    attributes=product.attributes,
                )
            )
    audit(
        db,
        tenant,
        actor,
        "product.updated" if product_id else "product.created",
        product.id,
        before,
        {field: getattr(product, field, None) for field in FIELDS},
    )
    db.flush()
    return product


def csv_export(products):
    data = io.StringIO()
    writer = csv.DictWriter(data, fieldnames=(*FIELDS, "parent_sku"))
    writer.writeheader()
    by_id = {p.id: p.sku for p in products}
    for product in products:
        row = {field: getattr(product, field) for field in FIELDS}
        row["parent_sku"] = by_id.get(product.parent_id, "")
        # Prevent spreadsheet formula execution while preserving text.
        for key, value in row.items():
            if isinstance(value, (list, dict)):
                row[key] = json.dumps(value, ensure_ascii=False)
            if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
                row[key] = "'" + value
        writer.writerow(row)
    return data.getvalue()
