"""One identified stock operation. Refuses to overwrite a newly changed store."""

from sqlalchemy import select
import os
from .database import transaction
from .catalog import product_for, audit
from .models import InventoryMovement, SyncEvent, GenerationJob, now
from . import queue


def sync_stock(job, owner):
    if os.getenv("STOCK_AUTHORITY", "app") != "app":
        raise ValueError(
            "La autoridad de stock cambió; se detuvo la escritura a WooCommerce."
        )
    from ecommerce_services import WooCommerceService

    woo = WooCommerceService()
    payload = dict(job["payload"])
    with transaction() as db:
        product = product_for(db, job["tenant_id"], job["product_id"])
        if product.version != payload["version"]:
            raise ValueError("El stock maestro cambió. Revisa y confirma otra vez.")
    data = woo.resolve(product)
    before = data.get("stock_quantity")
    quantity = payload["quantity"]
    if before is None or float(before) != float(payload["expected_remote"]):
        raise ValueError(
            "WooCommerce cambió desde la última consulta. Lee el stock y revisa la diferencia antes de enviar."
        )
    if quantity is None:
        raise ValueError("No existe una cantidad maestra para enviar.")
    payload["in_flight"] = {"operation": "woocommerce_stock", "quantity": quantity}
    queue.checkpoint(
        job["id"],
        owner,
        payload=payload,
        message="Enviando movimiento identificado de stock",
    )
    body = {
        "manage_stock": True,
        "stock_quantity": quantity,
        "meta_data": [{"key": "_rincon_inventory_event", "value": job["id"]}],
    }
    if product.woocommerce_variation_id:
        woo.client.update_variation(
            product.woocommerce_product_id, product.woocommerce_variation_id, body
        )
    else:
        woo.client.update_product(product.woocommerce_product_id, body)
    verified = woo.resolve(product)
    if (
        verified.get("stock_quantity") is None
        or float(verified["stock_quantity"]) != quantity
    ):
        raise ValueError(
            "La tienda no confirmó la cantidad. Verifica el evento antes de repetir."
        )
    with transaction() as db:
        p = product_for(db, job["tenant_id"], product.id, True)
        p.woocommerce_stock = quantity
        p.last_woocommerce_sync = now()
        p.sync_status = "synced" if p.stock == quantity else "difference"
        if not db.scalar(
            select(InventoryMovement.id).where(
                InventoryMovement.tenant_id == job["tenant_id"],
                InventoryMovement.source == "app-to-woocommerce",
                InventoryMovement.source_event_id == job["id"],
                InventoryMovement.product_id == p.id,
            )
        ):
            db.add(
                InventoryMovement(
                    tenant_id=job["tenant_id"],
                    product_id=p.id,
                    variant_id=p.id if p.parent_id else None,
                    source="app-to-woocommerce",
                    source_event_id=job["id"],
                    quantity_before=float(before),
                    quantity_after=quantity,
                    delta=quantity - float(before),
                    metadata_json={
                        "destination": "woocommerce",
                        "master_version": payload["version"],
                    },
                )
            )
        db.add(
            SyncEvent(
                tenant_id=job["tenant_id"],
                product_id=p.id,
                source="app",
                destination="woocommerce",
                action="Stock",
                status="completed",
                message="Cantidad y SKU verificados",
                job_id=job["id"],
            )
        )
        audit(
            db,
            job["tenant_id"],
            job["actor"],
            "stock.synchronized",
            p.id,
            {"woocommerce": before},
            {"woocommerce": quantity, "event_id": job["id"]},
        )
        stored = db.get(GenerationJob, job["id"])
        stored.payload = {**payload, "in_flight": None}
    return True
