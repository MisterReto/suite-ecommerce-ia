"""Transactional queue with leases and explicit handling of uncertain paid writes."""
# Estado durable de trabajos, locks, lease y cancelación segura entre operaciones.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import os
import time
import hashlib
from sqlalchemy import select, func
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
        from .redis_broker import reachable

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
def recover_expired(db):
    stamp = time.time()
    expired = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.status.in_(["processing", "cancelling"]), GenerationJob.lease_until < stamp)
        .with_for_update(skip_locked=True)
    ).all()
    for job in expired:
        if job.status == "cancelling":
            mark_cancelled(job)
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


# Reclama bajo lock un único trabajo En cola, le asigna propietario y lease de cinco minutos.
def claim(owner, job_id=None):
    stamp = time.time()
    with transaction() as db:
        recover_expired(db)
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
def checkpoint(job_id, owner, *, payload=None, progress=None, message=None):
    cancelled = False
    with transaction() as db:
        job = db.scalar(
            select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
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
        saving_result = payload is not None and job.payload.get("in_flight") and not payload.get("in_flight")
        if not cancelled or saving_result:
            job.lease_until = time.time() + 300
            if payload is not None:
                job.payload = payload
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
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id).with_for_update())
        if not job or job.status not in {"processing", "cancelling"} or job.lease_owner != owner or job.lease_until < time.time():
            raise RuntimeError("El trabajo ya no pertenece a este worker.")
        job.lease_until = time.time() + 300


# Guarda el resultado final del propietario vigente; Deteniendo termina como Cancelado y
# conserva el historial.
def finish(job_id, owner, success, message):
    with transaction() as db:
        job = db.scalar(
            select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
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
