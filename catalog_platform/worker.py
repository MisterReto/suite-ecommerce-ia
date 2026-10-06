"""One Render worker. Browser-independent jobs reuse the frozen studio pipeline."""

from copy import deepcopy
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import signal
import threading
import time
from PIL import Image
from sqlalchemy import select
from .database import transaction
from .models import (
    Product,
    ProductImage,
    GeneratedAsset,
    GenerationJob,
    SyncEvent,
    IntegrationMapping,
    now,
    uid,
)
from .accounts import load, persist
from .catalog import serialize, audit, product_for
from . import queue

log = logging.getLogger("rincon.worker")
STOP = threading.Event()
OWNER = secrets.token_urlsafe(24)


def generation(job, value, drive):
    from studio_api import runtime, asset, file_path
    from image_generation_service import ImageGenerationService
    from creative_pipeline import load_style_examples, plan_key

    service = ImageGenerationService()
    if job["model"] != service.provider.model:
        raise ValueError(
            "El modelo configurado cambió desde que se confirmó el trabajo. No se generó otra imagen."
        )
    payload = deepcopy(job["payload"])
    product = payload["product"]
    p = {
        "sku": product["sku"],
        "name": product["name"],
        "brand": product["brand"],
        "category": product["category"],
        "subcategory": product["subcategory"],
        "short_description": product["short_description"],
        "description": product["long_description"],
        "size": product.get("attributes", {}).get("Tamaño", ""),
    }
    references = []
    for index, file_id in enumerate(payload["references"]):
        path = f"/tmp/{value['file_namespace']}_reference_{index}.jpg"
        Path(path).write_bytes(drive.download(file_id))
        references.append(path)
    current = {"revision": uid(), "references": references, "product": p, "images": {}}
    value["capture_revision"] = current["revision"]

    def progress(count, message):
        queue.checkpoint(job["id"], OWNER, progress=count, message=message)

    if payload.get("previous_raw_id"):
        previous = f"/tmp/{value['file_namespace']}_previous.jpg"
        Path(previous).write_bytes(drive.download(payload["previous_raw_id"]))
        slot = payload["slots"][0]
        current["images"][slot] = {
            "raw_id": asset(value, previous),
            "history": payload.get("history", []),
        }
    if any(slot != "1_hd" for slot in payload["slots"]):
        if payload.get("brief"):
            paths, _ = load_style_examples(runtime, value)
            current.update(brief=payload["brief"], brief_key=plan_key(p, paths))
        plan, styles = service.plan(value, current, progress)
        payload["brief"] = plan
        queue.checkpoint(job["id"], OWNER, payload=payload)
    else:
        plan, styles = {}, []
    generated = drive.working_folder("images", "generated")
    targets = [
        (slot, index)
        for slot in payload["slots"]
        for index in range(1, payload["quantity"] + 1)
    ]
    completed = list(payload.get("completed_keys", []))
    for slot, index in targets:
        marker = f"{slot}:{index}"
        if marker in completed:
            continue
        if STOP.is_set():
            # No new paid call after SIGTERM; lease recovery resumes safe checkpoints.
            queue.checkpoint(
                job["id"],
                OWNER,
                payload=payload,
                message="En pausa por despliegue; se retomará desde el checkpoint.",
            )
            return False
        payload["in_flight"] = {
            "slot": slot,
            "sample": index,
            "operation": "image_generation",
        }
        queue.checkpoint(
            job["id"],
            OWNER,
            payload=payload,
            progress=int(len(completed) * 100 / len(targets)),
            message=f"Generando {product['sku']} · {slot} · {index}",
        )
        prompt = (
            runtime.PROMPT_HD
            if slot == "1_hd"
            else plan["lifestyle" if slot == "2_uso" else "comercial"]
        )
        item = service.generate(
            value,
            current,
            slot,
            prompt,
            styles,
            feedback=[payload["feedback"]] if payload.get("feedback") else (),
            automatic_review=payload.get("automatic_review", False),
        )
        output = file_path(value, item["id"])
        raw = file_path(value, item["raw_id"])
        image_bytes = Path(output).read_bytes()
        checksum = hashlib.sha256(image_bytes).hexdigest()
        with Image.open(output) as picture:
            width, height = picture.size
        prefix = f"{product['sku']}_{slot}_{job['id']}_{index}"
        branded = drive.upload(
            output,
            prefix + ".jpg",
            generated,
            {
                "job_id": job["id"],
                "slot": slot,
                "sample": str(index),
                "checksum": checksum,
            },
        )
        raw_file = drive.upload(
            raw, prefix + "_raw.jpg", generated, {"job_id": job["id"], "kind": "raw"}
        )
        with transaction() as db:
            image = ProductImage(
                tenant_id=job["tenant_id"],
                product_id=job["product_id"],
                drive_file_id=branded["id"],
                checksum=checksum,
                width=width,
                height=height,
                role={
                    "1_hd": "gallery",
                    "2_uso": "lifestyle",
                    "3_comercial": "commercial",
                }[slot],
                status="completed",
                metadata_json={
                    "provider": "gemini",
                    "model": job["model"],
                    "slot": slot,
                    "qa": item.get("qa"),
                    "filename": prefix + ".jpg",
                },
            )
            db.add(image)
            db.flush()
            record = GeneratedAsset(
                tenant_id=job["tenant_id"],
                job_id=job["id"],
                product_id=job["product_id"],
                image_id=image.id,
                raw_drive_file_id=raw_file["id"],
                slot=slot,
                sample=index,
                model=job["model"],
                history=item["history"],
                metadata_json={
                    "checksum": checksum,
                    "width": width,
                    "height": height,
                    "mime_type": "image/jpeg",
                    "qa": item.get("qa"),
                    "brief": plan,
                },
            )
            db.add(record)
            audit(
                db,
                job["tenant_id"],
                job["actor"],
                "image.generated",
                job["product_id"],
                after={
                    "job_id": job["id"],
                    "image_id": image.id,
                    "slot": slot,
                    "checksum": checksum,
                },
            )
            completed.append(marker)
            payload["completed_keys"] = completed
            payload["in_flight"] = None
            # Asset + checkpoint commit together; never spends another image on recovery.
            locked = db.scalar(
                select(GenerationJob)
                .where(GenerationJob.id == job["id"])
                .with_for_update()
            )
            if locked.lease_owner != OWNER or locked.status != "processing":
                raise RuntimeError("Se perdió el lease antes de guardar el resultado.")
            locked.payload = deepcopy(payload)
            locked.progress = int(len(completed) * 100 / len(targets))
            locked.lease_until = time.time() + 300
    return True


def publication(job, value, drive):
    from ecommerce_services import WordPressMediaService, WooCommerceService
    from woocommerce_product_sync import resolve_taxonomies

    media = WordPressMediaService()
    woo = WooCommerceService()
    with transaction() as db:
        product = product_for(db, job["tenant_id"], job["product_id"])
        if product.version != job["payload"]["version"]:
            raise ValueError(
                "El producto cambió después de confirmar. Revisa otra vez antes de publicar."
            )
        parent = (
            product_for(db, job["tenant_id"], product.parent_id)
            if product.parent_id
            else None
        )
        rows = db.scalars(
            select(ProductImage).where(
                ProductImage.tenant_id == job["tenant_id"],
                ProductImage.product_id == product.id,
                ProductImage.id.in_(job["payload"]["image_ids"]),
            )
        ).all()
        if len(rows) != len(job["payload"]["image_ids"]) or any(
            row.status not in {"approved", "published"} for row in rows
        ):
            raise ValueError(
                "La selección de imágenes aprobadas cambió. Confirma de nuevo."
            )
        images = [
            serialize(row)
            for row in sorted(rows, key=lambda r: 0 if r.role == "main" else 1)
        ]
    ids = []
    payload = deepcopy(job["payload"])
    for image in images:
        mid = image["metadata_json"].get("wordpress_media_id")
        if not mid:
            payload["in_flight"] = {
                "operation": "wordpress_upload",
                "image_id": image["id"],
            }
            queue.checkpoint(
                job["id"],
                OWNER,
                payload=payload,
                message="Subiendo imagen aprobada a WordPress",
            )
            result = media.upload(
                drive.download(image["drive_file_id"]),
                image["metadata_json"].get("filename", product.sku + ".jpg"),
                product.name,
            )
            mid = int(result["id"])
            with transaction() as db:
                row = db.get(ProductImage, image["id"])
                row.metadata_json = {
                    **row.metadata_json,
                    "wordpress_media_id": mid,
                    "wordpress_media_url": result.get("source_url", ""),
                }
            payload["in_flight"] = None
            queue.checkpoint(job["id"], OWNER, payload=payload)
        ids.append(mid)
    payload["in_flight"] = {"operation": "woocommerce_publish"}
    queue.checkpoint(
        job["id"], OWNER, payload=payload, message="Publicando producto en WooCommerce"
    )
    row = {
        "categorias": product.category
        + (" > " + product.subcategory if product.subcategory else ""),
        "etiquetas": ", ".join(product.tags),
        "Marca": product.brand,
    }
    terms = resolve_taxonomies(woo.client, row)
    taxonomy = {
        "categories": [{"id": i} for i in terms.get("category_ids", [])],
        "tags": [{"id": i} for i in terms.get("tag_ids", [])],
    }
    if terms.get("brand_ids"):
        taxonomy["brands"] = [{"id": i} for i in terms["brand_ids"]]
    result = woo.publish(product, ids, parent, taxonomy)
    # Verify by permanent ID before marking the local product published.
    remote = (
        woo.variation(parent.woocommerce_product_id, int(result["id"]))
        if parent
        else woo.product(int(result["id"]))
    )
    if str(remote.get("sku", "")) != product.sku or remote.get("status") != "publish":
        raise ValueError(
            "WooCommerce no confirmó SKU/estado. Revisa la operación antes de repetir."
        )
    with transaction() as db:
        stored = product_for(db, job["tenant_id"], product.id, True)
        if parent:
            stored.woocommerce_product_id = parent.woocommerce_product_id
            stored.woocommerce_variation_id = int(result["id"])
        else:
            stored.woocommerce_product_id = int(result["id"])
        stored.wordpress_media_ids = ids
        stored.status = "published"
        stored.sync_status = (
            "synced" if stored.version == product.version else "pending"
        )
        stored.last_woocommerce_sync = now()
        ext = str(result["id"])
        kind = "variation" if parent else "product"
        mapping = db.scalar(
            select(IntegrationMapping).where(
                IntegrationMapping.tenant_id == job["tenant_id"],
                IntegrationMapping.provider == "woocommerce",
                IntegrationMapping.entity_type == kind,
                IntegrationMapping.external_id == ext,
            )
        )
        if mapping and mapping.internal_product_id != product.id:
            raise ValueError(
                "El ID externo está asociado a otro producto; no se cambió el mapping."
            )
        if not mapping:
            db.add(
                IntegrationMapping(
                    tenant_id=job["tenant_id"],
                    internal_product_id=product.id,
                    provider="woocommerce",
                    entity_type=kind,
                    external_id=ext,
                    parent_external_id=(
                        str(parent.woocommerce_product_id) if parent else None
                    ),
                )
            )
        for image in images:
            db.get(ProductImage, image["id"]).status = "published"
            for asset in db.scalars(
                select(GeneratedAsset).where(GeneratedAsset.image_id == image["id"])
            ):
                asset.status = "published"
        db.add(
            SyncEvent(
                tenant_id=job["tenant_id"],
                product_id=product.id,
                source="app",
                destination="woocommerce",
                action="Publicación/actualización",
                status="completed",
                message="Producto y medios verificados",
                job_id=job["id"],
            )
        )
        audit(
            db,
            job["tenant_id"],
            job["actor"],
            "product.published",
            product.id,
            after={"woocommerce_id": result["id"], "media_ids": ids},
            system="woocommerce",
        )
        stored_job = db.get(GenerationJob, job["id"])
        stored_job.payload = {**payload, "in_flight": None}
    return True


def process(job):
    if job["kind"] == "webhook":
        from .webhooks import process_event

        return process_event(job, OWNER)
    import studio_api
    from drive_service import DriveService

    runtime = studio_api.runtime
    with transaction() as db:
        value = load(db, job["tenant_id"], job["actor"])
    sid = secrets.token_urlsafe(32)
    value.update(
        session_id=sid,
        file_namespace=secrets.token_urlsafe(24),
        expires_at=time.time() + 8 * 3600,
    )
    runtime.SESSIONS[sid] = value
    try:
        drive = DriveService.for_session(runtime, value)
        if drive.root_id != job["tenant_id"]:
            raise ValueError(
                "La carpeta de la conexión cambió; el trabajo quedó sin ejecutar."
            )
        if job["kind"] == "generation":
            done = generation(job, value, drive)
        elif job["kind"] == "publication":
            done = publication(job, value, drive)
        elif job["kind"] == "import":
            from .imports import execute_import

            done = execute_import(job, value, drive, OWNER)
        elif job["kind"] == "ecommerce_pull":
            from .ecommerce import refresh

            done = refresh(job, OWNER, value, drive)
        elif job["kind"] == "enrichment":
            from .enrichment import enrich

            done = enrich(job, OWNER, value, drive)
        elif job["kind"] == "stock_sync":
            from .inventory import sync_stock

            done = sync_stock(job, OWNER)
        else:
            raise ValueError("Tipo de trabajo no disponible.")
        with transaction() as db:
            persist(db, job["tenant_id"], job["actor"], value)
        return done
    except Exception as exc:
        from app_security import public_error

        raise RuntimeError(
            public_error(ValueError(studio_api.error_message(exc, value)))
        ) from None
    finally:
        runtime._eliminar_sesion(sid)


def main():
    from .security import cipher

    cipher()
    for name in (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "DATABASE_URL",
    ):
        if not os.getenv(name):
            raise RuntimeError("Falta " + name + "; no se inició el worker.")
    signal.signal(signal.SIGTERM, lambda *args: STOP.set())
    signal.signal(signal.SIGINT, lambda *args: STOP.set())
    logging.basicConfig(level=logging.INFO)

    def keeper():
        while not STOP.wait(15):
            try:
                queue.heartbeat(OWNER)
            except Exception:
                log.error(
                    "No se pudo renovar el heartbeat; se detienen nuevas adquisiciones."
                )
                STOP.set()

    queue.heartbeat(OWNER)
    thread = threading.Thread(target=keeper, daemon=True)
    thread.start()
    while not STOP.is_set():
        job = queue.claim(OWNER)
        if not job:
            STOP.wait(2)
            continue
        try:
            if process(job):
                queue.finish(
                    job["id"],
                    OWNER,
                    True,
                    "Completado. Revisa las imágenes antes de publicar.",
                )
        except Exception as exc:
            # Never emit payloads, credentials, raw provider errors or URLs with auth.
            from studio_api import error_message

            message = error_message(exc, {})
            queue.finish(job["id"], OWNER, False, message)
            with transaction() as db:
                if job["kind"] in {"publication", "stock_sync"}:
                    p = product_for(db, job["tenant_id"], job["product_id"])
                    p.sync_status = "error"
                    db.add(
                        SyncEvent(
                            tenant_id=job["tenant_id"],
                            product_id=p.id,
                            source="app",
                            destination="woocommerce",
                            action="Publicación",
                            status="failed",
                            message="No se confirmó la operación. Revisa antes de reintentar.",
                            job_id=job["id"],
                        )
                    )
                audit(
                    db,
                    job["tenant_id"],
                    job["actor"],
                    job["kind"] + ".failed",
                    job["product_id"],
                    after={"job_id": job["id"]},
                    result="failed",
                )
            log.warning(
                "Trabajo falló: tipo=%s; detalles disponibles en el panel", job["kind"]
            )
    log.info("Worker detenido; checkpoints guardados.")


if __name__ == "__main__":
    main()
