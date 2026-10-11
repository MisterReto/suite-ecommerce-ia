"""RQ transports only SQL job IDs. SQL checkpoints remain authoritative."""
# Entrega de IDs SQL a RQ y reconciliación de trabajos si Redis no recibió una entrega.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import logging
import os
from functools import lru_cache
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError, DuplicateJobError
from rq.serializers import JSONSerializer
from sqlalchemy import select
from .database import transaction
from .models import GenerationJob

log = logging.getLogger("rincon.queue")
QUEUE_NAME = "rincon-image-jobs"


# Construye/reutiliza la conexión Redis correspondiente a la URL configurada.
@lru_cache(maxsize=2)
def connection_for(url):
    if not url.startswith(("redis://", "rediss://", "unix://")):
        raise RuntimeError("REDIS_URL debe ser una conexión Redis válida.")
    return Redis.from_url(url, socket_connect_timeout=3, socket_timeout=5,
                          health_check_interval=30, max_connections=12)


# Obtiene Redis desde el entorno del proceso.
def connection():
    url = os.getenv("REDIS_URL", "")
    if not url:
        raise RuntimeError("Falta REDIS_URL; no se inició la cola RQ.")
    return connection_for(url)


# Comprueba disponibilidad de Redis sin consumir un trabajo.
def reachable():
    try:
        return bool(connection().ping())
    except (RedisError, RuntimeError, ValueError):
        return False


# Construye la cola RQ con serialización JSON.
def rq_queue():
    return Queue(QUEUE_NAME, connection=connection(), serializer=JSONSerializer)


# Entrega solo el UUID SQL, con deduplicación de despacho; no serializa fotos o credenciales.
def publish_one(job_id):
    client = connection()
    # Concurrent API/reconciler deliveries cannot enqueue the same ID together.
    with client.lock("rincon:dispatch:" + job_id, timeout=15, blocking_timeout=3):
        with transaction() as db:
            if db.scalar(select(GenerationJob.status).where(GenerationJob.id == job_id)) != "queued":
                return False
        rq_id = "rincon-" + job_id
        try:
            previous = Job.fetch(rq_id, connection=client, serializer=JSONSerializer)
        except NoSuchJobError:
            previous = None
        if previous:
            if previous.get_status() in {"queued", "started", "deferred", "scheduled"}:
                return False
            # Only SQL jobs explicitly queued again may get another delivery.
            # Interrupted paid operations are failed by recover_expired instead.
            previous.delete()
        try:
            rq_queue().enqueue(
                "catalog_platform.worker.execute_job", job_id,
                job_id=rq_id, unique=True,
                job_timeout=int(os.getenv("IMAGE_JOB_TIMEOUT_SECONDS", "1800")),
                result_ttl=3600, failure_ttl=86400,
                description="Trabajo de Suite Ecommerce IA",
            )
        except DuplicateJobError:
            return False
        return True


# Publica IDs de una transacción ya confirmada y conserva SQL como respaldo si Redis falla.
def publish_committed(ids):
    if os.getenv("GENERATION_QUEUE_BACKEND", "postgres") != "rq":
        return
    try:
        for job_id in ids:
            publish_one(job_id)
    except (RedisError, RuntimeError, ValueError):
        # The committed SQL outbox will be delivered by the supervisor later.
        # Never log the Redis URL, credentials or provider response.
        log.warning("Entrega RQ pendiente; el job permanece guardado en SQL.")


# Revisa la bandeja SQL En cola y recupera entregas pendientes; un trabajo Cancelado no
# vuelve a ejecutarse.
def reconcile():
    from .queue import recover_expired

    with transaction() as db:
        recover_expired(db)
        ids = list(db.scalars(select(GenerationJob.id)
                             .where(GenerationJob.status == "queued")
                             .order_by(GenerationJob.created_at).limit(100)))
    publish_committed(ids)
    return len(ids)
