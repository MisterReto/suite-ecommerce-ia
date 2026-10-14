"""Durable WooCommerce jobs reuse the accepted exporter; image generation stays separate."""
from copy import deepcopy
from contextlib import nullcontext
import html
import json
import time

from sqlalchemy import select
from . import queue
from .accounts import account, load, persist, put
from .catalog import audit
from .database import transaction
from .models import GenerationJob, uid
from .security import require_role, unseal
from .woocommerce_export import Exporter, connection_status, google_clients, store_url, safe_error

KIND = "woocommerce_export"


def public_job(job):
    message = job.message
    for _ in range(3):
        message = html.unescape(message)
    if ("woocommerce_rest_product_not_created" in message and "SKU" in message
            and any(text in message.lower() for text in ("tabla de b", "lookup table"))):
        message = "WooCommerce rechazó la creación: el SKU ya figura en la tabla de búsqueda. Revisa los productos y la papelera de la tienda antes de reintentar."
    elif "{" in message:
        try:
            detail = json.loads(message[message.index("{"):])
            if isinstance(detail.get("message"), str):
                message = detail["message"]
        except (ValueError, TypeError, AttributeError):
            pass
    message = html.unescape(safe_error(ValueError(message)))
    return {"id": job.id, "batch_id": job.batch_id, "status": job.status, "progress": job.progress,
        "message": message, "selection": job.payload.get("selection"),
        "events": job.payload.get("events", [])[-100:], "uncertain": bool(job.payload.get("in_flight")),
        "store": job.payload.get("store_url"), "created_at": job.created_at.isoformat() if job.created_at else None}


def enqueue(value, preview, request_key, batch_id=None, db=None):
    from fastapi import HTTPException
    require_role(value, "admin")
    status = connection_status()
    if not status["configured"] or preview["options"]["images"] and not status["images_configured"]:
        raise HTTPException(503, "Configura las variables de WooCommerce/WordPress indicadas en Conexión.")
    with (transaction() if db is None else nullcontext(db)) as db:
        queue.request_lock(db, value["platform_tenant"], "wc-request:" + request_key)
        existing = db.scalar(select(GenerationJob).where(
            GenerationJob.tenant_id == value["platform_tenant"], GenerationJob.actor == value["email"],
            GenerationJob.kind == KIND, GenerationJob.request_key == request_key))
        if existing:
            if existing.payload.get("preview_token") != preview["token"]:
                raise HTTPException(409, "La clave de solicitud ya identifica otra selección.")
            return public_job(existing)
        if not queue.available(db):
            raise HTTPException(503, "No hay worker disponible para recibir la carga.")
        payload = {"selection": preview["selection"], "options": preview["options"],
            "source": deepcopy(preview["source"]), "preview_token": preview["token"],
            "store_url": preview["store_url"], "bulk_token": preview.get("bulk_token"),
            "events": [], "remote_effects": [], "in_flight": None}
        job = GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"], kind=KIND,
            request_key=request_key, provider="woocommerce", model="colab-exporter-v1", estimated_cost=0,
            payload=payload, batch_id=batch_id, message="En cola para cargar en WooCommerce")
        db.add(job)
        persist(db, value["platform_tenant"], value["email"], value)
        queue.dispatch(db, job)
        audit(db, value["platform_tenant"], value["email"], "woocommerce.export.queued",
              after={"job_id": job.id, "selection": payload["selection"]})
        return public_job(job)


def process(job, owner):
    payload = deepcopy(job["payload"])
    if payload["store_url"] != store_url():
        raise ValueError("La tienda cambió después de la vista previa. Revisa y crea una carga nueva.")
    with transaction() as db:
        value = load(db, job["tenant_id"], job["actor"])
        record = account(db, job["tenant_id"], job["actor"], "woocommerce_media_cache")
        cache = unseal(record.encrypted_credentials) if record and record.status == "connected" else {}
    value.update(email=job["actor"], platform_tenant=job["tenant_id"])
    require_role(value, "admin")
    from studio_api import runtime
    drive = runtime._get_drive_service(value)
    source = payload["source"]
    for effect in payload.get("remote_effects", []):
        if effect.get("filename") and effect.get("id"):
            for image in source.get("ARCHIVOS", []):
                if image["name"] == effect["filename"]:
                    cache[store_url() + "|" + image["id"]] = effect["id"]

    def checkpoint(message=None):
        queue.checkpoint(job["id"], owner, payload=deepcopy(payload), message=message)

    def before(operation, modifying):
        if modifying:
            payload["in_flight"] = operation
        checkpoint("Cargando " + payload["selection"]["sku"] + "…")

    def after(operation, modifying, response):
        if not modifying:
            return
        if 200 <= response.status_code < 300:
            try:
                result = response.json()
            except ValueError:
                return  # Keep uncertainty when an accepted write has no readable result.
            if isinstance(result, dict) and result.get("id"):
                payload["remote_effects"].append({**operation, "id": result["id"]})
            else:
                return
            payload["in_flight"] = None
            checkpoint()
        elif 400 <= response.status_code < 500:
            payload["in_flight"] = None
            checkpoint()

    def event(data):
        payload["events"].append(data)
        done = sum(item["action"] in {"producto_creado", "omitido_existente", "familia_creada",
                   "familia_existente", "variante_creada", "variante_omitida"} for item in payload["events"])
        total = len(source.get("VARIANTES", {})) + 1
        queue.checkpoint(job["id"], owner, payload=deepcopy(payload),
            progress=min(95, int(done * 95 / max(1, total))), message="WooCommerce: " + data["action"])

    def media_cache(data):
        with transaction() as db:
            queue.request_lock(db, job["tenant_id"], "wc-cache:" + job["actor"])
            record = account(db, job["tenant_id"], job["actor"], "woocommerce_media_cache")
            current = unseal(record.encrypted_credentials) if record and record.status == "connected" else {}
            current.update(data)
            put(db, job["tenant_id"], job["actor"], "woocommerce_media_cache", current)
        payload["media_cache"] = data
        checkpoint()

    engine = Exporter(source, drive, write=True, before=before, after=after,
                      on_event=event, on_cache=media_cache, media_cache=cache)
    try:
        selection = payload["selection"]
        parent, _, _ = engine.ns["resolver"]({"simple": "Simple", "family": "Familia", "variant": "Variante"}[selection["kind"]], selection["sku"])
        # All actors/stores use the same SQL lock for this remote family, including retries.
        with transaction() as db:
            queue.request_lock(db, "woocommerce:" + store_url(), parent["sku"])
            engine.execute(selection["kind"], selection["sku"], payload["options"])
        payload["in_flight"] = None
        checkpoint("Carga terminada. Los productos nuevos quedaron en borrador.")
        with transaction() as db:
            audit(db, job["tenant_id"], job["actor"], "woocommerce.export.completed",
                  after={"job_id": job["id"], "selection": selection})
            persist(db, job["tenant_id"], job["actor"], value)
        return True
    except queue.JobCancelled:
        raise
    except Exception as exc:
        raise ValueError(safe_error(exc)) from None
    finally:
        engine.close()
