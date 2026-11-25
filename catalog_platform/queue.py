"""Transactional queue with leases and explicit handling of uncertain paid writes."""
# Estado durable de trabajos, locks, lease y cancelación segura entre operaciones.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import os
import time
import hashlib
from sqlalchemy import select, func, update, cast, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import load_only
from .database import transaction
from .models import GenerationJob, WorkerHeartbeat, now


# Excepción de control: detener un trabajo no equivale a fallo ni autoriza un reintento.
class JobCancelled(RuntimeError):
    """A durable user request stops the next operation, without a retry."""


# Finaliza como Cancelado, libera el lease y conserva resultados e incertidumbre de una
# operación iniciada.
def mark_cancelled(job):
    job.status = "cancelled"
    job.message = (
        "Detenido. La operación iniciada tiene resultado incierto; revisa antes de iniciar otra."
        if job.payload.get("in_flight")
        else "Detenido. Se conservaron los resultados ya terminados."
    )
    job.lease_owner = None
    job.lease_until = None
    job.finished_at = now()


# Con la fila bloqueada, cancela En cola al instante o marca Deteniendo si hay una llamada
# vigente; no requiere Redis.
def request_cancel(job):
    """Caller holds the SQL row lock; this needs neither Redis nor a worker."""
    if job.status == "queued":
        mark_cancelled(job)
    elif job.status in {"processing", "cancelling"} and (
        not job.lease_owner or job.lease_until is None or job.lease_until < time.time()
    ):
        mark_cancelled(job)
    elif job.status == "processing":
        job.status = "cancelling"
        job.message = "Deteniendo. Esperando que termine la operación ya iniciada."


# Serializa solicitudes con la misma clave dentro del tenant mediante un lock PostgreSQL.
def request_lock(db, tenant, key):
    # Serializes duplicate HTTP submissions, including jobs without product_id.
    if db.bind.dialect.name == "postgresql":
        number = int.from_bytes(
            hashlib.sha256((tenant + ":" + key).encode()).digest()[:8],
            "big",
            signed=True,
        )
        db.execute(select(func.pg_advisory_xact_lock(number)))


# Registra que el supervisor sigue activo y la versión que ejecuta.
def heartbeat(owner):
    with transaction() as db:
        record = db.get(WorkerHeartbeat, owner)
        if record:
            record.updated = time.time()
        else:
            db.add(
                WorkerHeartbeat(
                    id=owner,
                    updated=time.time(),
                    version=os.getenv("RENDER_GIT_COMMIT", "local"),
                )
            )


# Comprueba Redis cuando corresponde y un heartbeat de menos de noventa segundos.
def worker_ready(db):
    if os.getenv("GENERATION_QUEUE_BACKEND", "postgres") == "rq":
        from .redis_broker import reachable, supervisor_alive

        if supervisor_alive():
            return True
        if not reachable():
            return False
    return (
        db.scalar(
            select(WorkerHeartbeat.id)
            .where(WorkerHeartbeat.updated > time.time() - 90)
            .limit(1)
        )
        is not None
    )


# Permite aceptar en SQL un trabajo para un worker gratuito que puede despertarse; no afirma
# que ya esté ejecutándose.
def available(db):
    if worker_ready(db):
        return True
    # A dormant free web worker can consume the durable SQL outbox after wakeup.
    # Legacy/dedicated workers retain the existing fail-closed readiness check.
    from .worker_wakeup import configured
    return configured()


# Registra el ID para su entrega posterior al commit; no ejecuta el trabajo dentro de la
# petición HTTP.
def dispatch(db, job):
    """Ask the transaction to deliver this job ID after a successful commit."""
    db.flush()
    db.info.setdefault("dispatch_ids", set()).add(job.id)


# Recupera leases vencidos; nunca reencola cancelados ni repite automáticamente una operación
# con resultado incierto.
def recover_expired(db, job_id=None):
    stamp = time.time()
    query = (
        select(GenerationJob)
        .where(GenerationJob.status.in_(["processing", "cancelling"]), GenerationJob.lease_until < stamp)
        .with_for_update(skip_locked=True)
    )
    if job_id is not None:
        query = query.where(GenerationJob.id == job_id)
    for job in db.scalars(query.limit(100)):
        if job.status == "cancelling":
            mark_cancelled(job)
        elif job.kind == "wc_reconcile" and job.payload.get("preview"):
            job.status = "failed"
            job.finished_at = now()
            job.message = "Sincronización interrumpida. Revisa los resultados y genera una nueva vista previa."
        elif job.payload.get("in_flight"):
            job.status = "failed"
            job.finished_at = now()
            job.message = "Operación interrumpida con resultado incierto. Revisa los archivos antes de autorizar otro intento."
        else:
            job.status = "queued"
            job.message = "Recuperado después de reinicio; conserva las imágenes terminadas."
        job.lease_owner = None
        job.lease_until = None
    db.flush()


def reserve_publication(db, job):
    # The store SKU is shared across tenants. Persist the reservation on the SQL
    # job so it follows the existing lease, cancellation and crash recovery.
    payload = job.payload
    selection = payload.get("selection") or {}
    sku = selection.get("sku", "")
    if selection.get("kind") == "variant":
        source = payload.get("source", {})
        sku = (source.get("VARIANTES", {}).get(sku, {}).get("sku_padre")
               or source.get("CSV_VARIANTES", {}).get(sku, {}).get("Superior") or "").strip()
    store = payload.get("store_url", "")
    key = hashlib.sha256((store + "\0" + sku.casefold()).encode()).hexdigest()
    request_lock(db, "woocommerce:" + store, sku.casefold())
    reservation = GenerationJob.payload["wc_family"].as_string()
    busy = db.scalar(select(GenerationJob.id).where(
        GenerationJob.kind == "woocommerce_export",
        GenerationJob.status.in_(["processing", "cancelling"]),
        # An active job from the old worker has no reservation field.
        or_(reservation == key, reservation.is_(None))).limit(1))
    if busy:
        return False
    job.payload = {**payload, "wc_family": key}
    return True


# Reclama bajo lock un único trabajo En cola, le asigna propietario y lease de cinco minutos.
def claim(owner, job_id=None):
    stamp = time.time()
    with transaction() as db:
        recover_expired(db, job_id)
        query = select(GenerationJob).where(GenerationJob.status == "queued")
        if job_id is not None:
            query = query.where(GenerationJob.id == job_id)
        job = db.scalar(
            query
            .order_by(GenerationJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        if job.kind == "woocommerce_export" and not reserve_publication(db, job):
            return None  # SQL stays queued for the outbox to deliver again.
        job.status = "processing"
        job.lease_owner = owner
        job.lease_until = stamp + 300
        job.started_at = job.started_at or now()
        db.flush()
        return {
            key: getattr(job, key)
            for key in (
                "id",
                "tenant_id",
                "actor",
                "kind",
                "product_id",
                "payload",
                "model",
            )
        }


# Persiste progreso/resultado y comprueba propietario/cancelación antes del siguiente paso;
# confirma SQL antes de lanzar JobCancelled.
def checkpoint(job_id, owner, *, payload=None, progress=None, message=None, updates=None):
    cancelled = False
    with transaction() as db:
        job = db.scalar(
            select(GenerationJob).options(load_only(
                GenerationJob.status, GenerationJob.lease_owner, GenerationJob.lease_until
            )).where(GenerationJob.id == job_id).with_for_update()
        )
        if (
            not job
            or job.status not in {"processing", "cancelling"}
            or job.lease_owner != owner
            or job.lease_until < time.time()
        ):
            raise RuntimeError(
                "El trabajo ya no pertenece a este worker. No se inició otra operación."
            )
        cancelled = job.status == "cancelling"
        # An already authorized operation may save its result. A cancellation
        # never authorizes a new in_flight operation. Commit before raising so
        # the result/cancellation cannot be rolled back by the worker exception.
        changes = updates if updates is not None else payload
        saving_result = (cancelled and changes is not None and (payload is not None or "in_flight" in changes)
                         and not changes.get("in_flight") and job.payload.get("in_flight"))
        if not cancelled or saving_result:
            job.lease_until = time.time() + 300
            if payload is not None:
                job.payload = payload
            elif updates:
                if not cancelled and db.bind.dialect.name == "postgresql":
                    job.payload = cast(GenerationJob.payload, JSONB).op("||")(cast(updates, JSONB))
                else:
                    job.payload = {**job.payload, **updates}
            if progress is not None:
                job.progress = progress
            if message is not None:
                job.message = str(message)[:500]
        if cancelled:
            mark_cancelled(job)
    if cancelled:
        raise JobCancelled("Trabajo detenido por el usuario.")


# Renueva el lease de una llamada en curso, incluso mientras se espera su cancelación.
def renew(job_id, owner):
    """Keep an in-flight call leased while cancellation waits for its result."""
    with transaction() as db:
        stamp = time.time()
        result = db.execute(update(GenerationJob).where(
            GenerationJob.id == job_id, GenerationJob.status.in_(["processing", "cancelling"]),
            GenerationJob.lease_owner == owner, GenerationJob.lease_until >= stamp
        ).values(lease_until=stamp + 300))
        if not result.rowcount:
            raise RuntimeError("El trabajo ya no pertenece a este worker.")


# Guarda el resultado final del propietario vigente; Deteniendo termina como Cancelado y
# conserva el historial.
def finish(job_id, owner, success, message):
    with transaction() as db:
        job = db.scalar(
            select(GenerationJob).options(load_only(GenerationJob.lease_owner, GenerationJob.status,
                GenerationJob.kind)).where(GenerationJob.id == job_id).with_for_update()
        )
        if job and job.lease_owner == owner and job.status == "cancelling":
            mark_cancelled(job)
        elif job and job.lease_owner == owner and job.status == "processing":
            job.status = (
                ("published" if job.kind == "publication" else "completed")
                if success
                else "failed"
            )
            job.message = message[:500]
            if success:
                job.progress = 100
            job.lease_owner = None
            job.lease_until = None
            job.finished_at = now()
