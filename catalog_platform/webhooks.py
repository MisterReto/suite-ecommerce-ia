"""Signed, durable and idempotent webhook intake. Heavy work follows in the queue."""

import base64
import hashlib
import hmac
import json
import os
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .database import configured, transaction
from .models import (
    WebhookEvent,
    GenerationJob,
    Product,
    InventoryMovement,
    SyncEvent,
    now,
)
from .security import seal, unseal
from .catalog import move_stock, audit
from . import queue

router = APIRouter()


def signature_valid(raw, signature, secret):
    expected = base64.b64encode(
        hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    ).decode()
    return bool(signature) and hmac.compare_digest(expected, signature)


async def receive(provider, request):
    if not configured():
        raise HTTPException(503, "La recepción durable aún no está configurada.")
    secret = os.getenv(
        (
            "WOOCOMMERCE_WEBHOOK_SECRET"
            if provider == "woocommerce"
            else "LOYVERSE_WEBHOOK_SECRET"
        ),
        "",
    )
    tenant = os.getenv("WEBHOOK_TENANT_ID", "")
    if not secret or not tenant:
        raise HTTPException(
            503, "Configura firma y carpeta de integración antes de activar webhooks."
        )
    if provider == "loyverse":
        # Deliberately inert until the real account's signing contract is validated.
        raise HTTPException(
            503,
            "Loyverse está preparado; su recepción aún requiere validar la cuenta y firma del proveedor.",
        )
    raw = await request.body()
    if len(raw) > 512000:
        raise HTTPException(413, "Evento demasiado grande.")
    if not signature_valid(
        raw, request.headers.get("x-wc-webhook-signature", ""), secret
    ):
        raise HTTPException(401, "Firma de webhook inválida.")
    event_id = request.headers.get("x-wc-webhook-delivery-id", "")
    topic = request.headers.get("x-wc-webhook-topic", "")
    if not event_id or len(event_id) > 200:
        raise HTTPException(422, "Falta ID de entrega del evento.")
    try:
        data = json.loads(raw)
    except ValueError:
        raise HTTPException(422, "JSON inválido.") from None
    if not isinstance(data, dict):
        raise HTTPException(422, "El evento debe ser un objeto.")
    checksum = hashlib.sha256(raw).hexdigest()
    try:
        with transaction() as db:
            old = db.scalar(
                select(WebhookEvent).where(
                    WebhookEvent.provider == provider, WebhookEvent.event_id == event_id
                )
            )
            if old:
                if old.payload_hash != checksum:
                    raise HTTPException(
                        409, "El ID del evento ya existe con otro contenido."
                    )
                return {"accepted": True, "duplicate": True}
            event = WebhookEvent(
                tenant_id=tenant,
                provider=provider,
                event_id=event_id,
                event_type=topic[:100],
                payload_hash=checksum,
                encrypted_payload=seal(data),
            )
            db.add(event)
            db.flush()
            db.add(
                GenerationJob(
                    tenant_id=tenant,
                    actor="webhook",
                    kind="webhook",
                    provider=provider,
                    request_key="webhook:"
                    + hashlib.sha256((provider + ":" + event_id).encode()).hexdigest(),
                    payload={"event_id": event.id},
                )
            )
            return {"accepted": True}
    except IntegrityError:
        with transaction() as db:
            old = db.scalar(
                select(WebhookEvent).where(
                    WebhookEvent.provider == provider, WebhookEvent.event_id == event_id
                )
            )
            if old and old.payload_hash != checksum:
                raise HTTPException(
                    409, "El ID del evento ya existe con otro contenido."
                )
            if not old and not db.scalar(
                select(WebhookEvent.id).where(
                    WebhookEvent.tenant_id == tenant,
                    WebhookEvent.provider == provider,
                    WebhookEvent.payload_hash == checksum,
                )
            ):
                raise
        return {"accepted": True, "duplicate": True}


@router.post("/webhooks/woocommerce", status_code=202)
async def woocommerce(request: Request):
    return await receive("woocommerce", request)


@router.post("/webhooks/loyverse", status_code=202)
async def loyverse(request: Request):
    return await receive("loyverse", request)


def process_event(job, owner):
    with transaction() as db:
        event = db.scalar(
            select(WebhookEvent)
            .where(WebhookEvent.id == job["payload"]["event_id"])
            .with_for_update()
        )
        if not event or event.status == "completed":
            return True
        data = unseal(event.encrypted_payload)
        if event.event_type.startswith("product."):
            # Permanent ID is authoritative. SKU fallback only discovers an unmapped item.
            product = db.scalar(
                select(Product)
                .where(
                    Product.tenant_id == event.tenant_id,
                    Product.woocommerce_product_id == data.get("id"),
                    Product.woocommerce_variation_id.is_(None),
                )
                .with_for_update()
            )
            if product and product.sku == str(data.get("sku", "")):
                from .ecommerce import apply_snapshot

                apply_snapshot(db, product, data, event.event_id, job["actor"])
                db.add(
                    SyncEvent(
                        tenant_id=event.tenant_id,
                        product_id=product.id,
                        source="woocommerce",
                        destination="app",
                        action=event.event_type,
                        status="completed",
                        message="Evento verificado e idempotente",
                    )
                )
        elif event.event_type.startswith("order."):
            from .ecommerce import store_order

            store_order(db, event.tenant_id, data)
        event.status = "completed"
        event.processed_at = now()
        audit(
            db,
            event.tenant_id,
            job["actor"],
            "webhook.processed",
            after={
                "provider": event.provider,
                "event_id": event.event_id,
                "event_type": event.event_type,
            },
        )
    return True
