"""One reviewed selection per durable job. Account-wide locks prevent local races."""
from copy import deepcopy
import json
import time
from fastapi import HTTPException
from sqlalchemy import select
from . import queue
from .accounts import persist, put, load
from .catalog import audit
from .database import transaction
from .models import GenerationJob, GenerationBatch, uid, now
from .security import require_role
from .loyverse_connections import JOB_PROVIDER, job_credentials, selected
from .loyverse_export import Exporter, fingerprint

KIND = "loyverse_export"
MAX_ATTEMPTS = 3


def public_job(job):
    p = job.payload
    return {"id": job.id, "batch_id": job.batch_id, "status": job.status, "progress": job.progress,
        "selection": p["selection"], "connection_name": p["connection_name"], "store_name": p["store_name"],
        "message": job.message, "events": p.get("events", [])[-100:],
        "uncertain": bool(p.get("in_flight")), "attempts": p.get("attempts", 1),
        "log_saved": bool(p.get("log_saved")), "pause_requested": bool(p.get("pause_requested"))}


def owned(db, value, job_id):
    job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id,
        GenerationJob.tenant_id == value["platform_tenant"], GenerationJob.actor == value["email"],
        GenerationJob.kind == KIND).with_for_update())
    if not job:
        raise HTTPException(404, "Carga Loyverse no disponible.")
    return job


def enqueue(value, preview, request_key):
    require_role(value, "admin")
    tenant, actor = value["platform_tenant"], value["email"]
    key = "ly:" + request_key
    with transaction() as db:
        queue.request_lock(db, tenant, key)
        old = db.scalar(select(GenerationBatch).where(GenerationBatch.tenant_id == tenant,
            GenerationBatch.request_key == key))
        if old:
            jobs = db.scalars(select(GenerationJob).where(GenerationJob.batch_id == old.id)).all()
            if old.actor != actor or any(j.payload.get("preview_token") != preview["token"] for j in jobs):
                raise HTTPException(409, "Esta solicitud ya corresponde a otro lote.")
            return {"batch_id": old.id, "jobs": [public_job(j) for j in jobs]}
        connection = selected(db, value, preview["connection_id"], preview["store_id"])
        if connection["revision"] != preview["revision"]:
            raise HTTPException(409, "La conexión cambió. Revisa el lote de nuevo.")
        if not queue.available(db):
            raise HTTPException(503, "El worker no está disponible para aceptar cargas.")
        batch = GenerationBatch(tenant_id=tenant, actor=actor, request_key=key,
            product_count=len(preview["entries"]), image_count=0, estimated_cost=0)
        db.add(batch)
        db.flush()
        persist(db, tenant, actor, value)
        jobs = []
        for entry in preview["entries"]:
            p = {"selection": entry["selection"], "source": deepcopy(entry["source"]),
                "options": preview["options"], "connection_id": connection["id"],
                "merchant_id": connection["merchant_id"], "store_id": preview["store_id"],
                "connection_name": connection["name"], "store_name": preview["store_name"],
                "preview_token": preview["token"], "part": entry.get("part", 0), "events": [], "image_tasks": [],
                "in_flight": None, "attempts": 1}
            job = GenerationJob(id=uid(), tenant_id=tenant, actor=actor, kind=KIND,
                batch_id=batch.id, request_key=key + ":" + fingerprint([entry["selection"], entry.get("part", 0)])[:16],
                provider="loyverse", model="accepted-colab-v1", estimated_cost=0,
                payload=p, message="En cola para publicar en Loyverse")
            db.add(job)
            # Never put even ciphertext credentials in a job payload returned by generic APIs.
            put(db, tenant, job.id, JOB_PROVIDER, connection)
            queue.dispatch(db, job)
            jobs.append(public_job(job))
        audit(db, tenant, actor, "loyverse.batch.queued", after={"batch_id": batch.id, "count": len(jobs)})
        return {"batch_id": batch.id, "jobs": jobs}


class Paused(RuntimeError):
    pass


def process(job, owner):
    p = deepcopy(job["payload"])
    with transaction() as db:
        value = load(db, job["tenant_id"], job["actor"])
        credentials = job_credentials(db, job)
    value.update(email=job["actor"], platform_tenant=job["tenant_id"])
    require_role(value, "admin")
    engine = None

    def checkpoint(message=None):
        # Atomically preserve concurrent pause/cancel requests and acknowledged remote effects.
        cancelled = False
        with transaction() as db:
            row = db.scalar(select(GenerationJob).where(GenerationJob.id == job["id"]).with_for_update())
            if not row or row.lease_owner != owner or row.status not in {"processing", "cancelling"} or row.lease_until < time.time():
                raise ValueError("La carga ya no pertenece a este worker.")
            p["pause_requested"] = bool(row.payload.get("pause_requested"))
            cancelled = row.status == "cancelling"
            saving_result = row.payload.get("in_flight") and not p.get("in_flight")
            if not cancelled or saving_result:
                row.payload = deepcopy(p)
                row.lease_until = time.time() + 300
                if message: row.message = message[:500]
            if cancelled: queue.mark_cancelled(row)
        if cancelled:
            raise queue.JobCancelled("Carga detenida por el usuario.")

    def guard():
        checkpoint()
        if p.get("pause_requested"):
            raise Paused()

    def before(op, modifying):
        guard()
        if modifying:
            with transaction() as db:
                job_credentials(db, job)  # Deleting a connection stops its next write.
            p["in_flight"] = deepcopy(op)
            checkpoint("Publicando " + p["selection"]["sku"])

    def after(op, modifying, response):
        if not modifying:
            return
        if 200 <= response.status_code < 300:
            if op["endpoint"].endswith("/image"):
                item_id = op["endpoint"].split("/")[1]
                for task in p["image_tasks"]:
                    if task["item_id"] == item_id:
                        task["done"] = True
            else:
                try:
                    remote = response.json()
                except ValueError:
                    return  # Keep uncertainty if acknowledgment cannot be decoded.
                remote_id = remote.get("id") or remote.get("variant_id")
                if not remote_id:
                    return
                if op["endpoint"] == "items" and p["options"]["images"]:
                    parent, chosen, _ = engine.resolve(p["selection"])
                    image = engine.ns["imagen_principal"](parent["sku"])
                    if not image and chosen:
                        image = engine.ns["imagen_principal"](chosen[0]["sku"])
                    if image:
                        p["image_tasks"].append({"item_id": remote_id, "file": image, "done": False})
            p["in_flight"] = None
            checkpoint()
        elif 400 <= response.status_code < 500:
            p["in_flight"] = None
            checkpoint()

    def event(action, sku, message):
        # Messages originate in the preserved core. Provider errors are sanitized at HTTP boundary.
        p["events"].append({"action": action, "sku": sku, "message": str(message)[:500], "at": time.time()})
        p["events"] = p["events"][-200:]
        checkpoint("Loyverse: " + action + " · " + sku)
        queue.checkpoint(job["id"], owner, progress=min(95, len(p["events"]) * 10))

    def save_log():
        from drive_service import DriveService
        from studio_api import runtime
        drive = DriveService.for_session(runtime, value)
        folder = drive.folder("Publicaciones_Loyverse")
        folder = drive.folder(fingerprint(credentials["merchant_id"])[:16], folder)
        raw = json.dumps({"connection": p["connection_name"], "store": p["store_name"],
            "selection": p["selection"], "attempt": p["attempts"], "events": p["events"]},
            ensure_ascii=False, indent=2).encode()
        drive.upload_bytes(raw, "loyverse_" + job["id"] + "_" + str(p["attempts"]) + ".json", folder, "application/json")
        p["log_saved"] = True
        with transaction() as db:
            row = db.get(GenerationJob, job["id"])
            if row and (row.lease_owner == owner or row.status in {"paused", "cancelled"}):
                row.payload = {**row.payload, "log_saved": True}

    try:
        engine = Exporter(credentials["token"], source=p["source"], write=True,
            store_id=p["store_id"], stores=[s["id"] for s in credentials["stores"]], before=before, after=after)
        from .loyverse_export import google_clients
        _, drive = google_clients(value)
        engine.bind_drive(drive)
        # All connections/users pointing at the same merchant serialize creation together.
        with transaction() as lock_db:
            queue.request_lock(lock_db, "loyverse-account", credentials["merchant_id"])
            identity = engine.identity()
            if identity["merchant_id"] != p["merchant_id"] or p["store_id"] not in {s["id"] for s in identity["stores"]}:
                raise ValueError("La cuenta o sucursal cambió. No se publicó ningún producto nuevo.")
            engine.session.stores = [s["id"] for s in identity["stores"]]
            engine.remote()  # Fresh account-wide SKUs before every execution/retry/resume.
            engine.review(p["selection"], p["options"])
            if p.get("in_flight"):
                p["in_flight"] = None
                event("reconciliado", p["selection"]["sku"], "Se volvió a consultar el catálogo antes de reintentar.")
            # A failed image must be retriable even though its successfully created SKU now exists.
            for task in p["image_tasks"]:
                if not task["done"]:
                    engine.ns["subir_imagen"](task["item_id"], task["file"])
                    event("imagen", p["selection"]["sku"], task["file"]["name"])
            engine.execute(p["selection"], p["options"], event)
            guard()
            if any(not task["done"] for task in p["image_tasks"]):
                raise ValueError("El artículo se creó; su imagen falló. Reintenta este elemento para completar la imagen.")
            checkpoint("Carga Loyverse terminada. Inventario y precios existentes conservados.")
        with transaction() as db:
            audit(db, job["tenant_id"], job["actor"], "loyverse.export.completed", after={"job_id": job["id"]})
        return True
    except Paused:
        with transaction() as db:
            row = db.scalar(select(GenerationJob).where(GenerationJob.id == job["id"]).with_for_update())
            if row.lease_owner == owner and row.status == "processing":
                row.status, row.message = "paused", "En pausa. Se conservaron los resultados terminados."
                row.lease_owner = row.lease_until = None
        return False
    finally:
        if engine:
            engine.close()
        try:
            save_log()
        except Exception:
            # SQL event history remains authoritative if Google Drive is unavailable.
            with transaction() as db:
                row = db.get(GenerationJob, job["id"])
                if row and row.lease_owner == owner:
                    row.payload = {**row.payload, "log_saved": False}


def control(value, job_id, action, confirmed=False):
    require_role(value, "admin")
    with transaction() as db:
        job = owned(db, value, job_id)
        if action == "cancel":
            if job.status == "paused": job.status = "queued"
            queue.request_cancel(job)
        elif action == "pause":
            if job.status == "queued":
                job.status, job.message = "paused", "En pausa antes de publicar."
            elif job.status == "processing":
                job.payload = {**job.payload, "pause_requested": True}
                job.message = "Pausando al terminar la operación iniciada."
        elif action in {"resume", "retry"}:
            required = "paused" if action == "resume" else "failed"
            if job.status == "queued":
                return public_job(job)  # Lost control-response cannot repeat a dispatch/attempt.
            if job.status != required or not confirmed:
                raise HTTPException(422, "Confirma la acción sobre un trabajo " + required + ".")
            credentials = job_credentials(db, {"id": job.id, "tenant_id": job.tenant_id,
                "actor": job.actor, "payload": job.payload})
            attempts = job.payload.get("attempts", 1)
            if action == "retry" and attempts >= MAX_ATTEMPTS:
                raise HTTPException(422, "Se alcanzaron tres intentos. Revisa el error antes de preparar otra publicación.")
            if not queue.available(db):
                raise HTTPException(503, "No hay worker disponible.")
            job.payload = {**job.payload, "pause_requested": False,
                "attempts": attempts + int(action == "retry")}
            job.status, job.message, job.finished_at = "queued", "En cola; se volverán a comprobar los SKU.", None
            queue.dispatch(db, job)
        audit(db, value["platform_tenant"], value["email"], "loyverse.job." + action, after={"job_id": job.id})
        return public_job(job)
