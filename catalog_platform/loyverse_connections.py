"""Personal, encrypted multi-account connections; no global Loyverse token."""
from copy import deepcopy
import time
from fastapi import HTTPException
from sqlalchemy import select
from .accounts import account, put
from .catalog import audit
from .models import GenerationJob
from .queue import request_lock, request_cancel
from .security import seal, unseal

PROVIDER = "loyverse_connections"
JOB_PROVIDER = "loyverse_job"


def connections(db, tenant, actor, lock=False):
    if lock:
        request_lock(db, tenant, "loyverse-connections:" + actor.casefold())
    record = account(db, tenant, actor, PROVIDER)
    return unseal(record.encrypted_credentials) if record else {}


def public_connection(row):
    return {key: deepcopy(row.get(key)) for key in (
        "id", "name", "merchant_name", "stores", "default_store_id", "status", "checked_at", "revision")}


def selected(db, value, connection_id, store_id=None):
    row = connections(db, value["platform_tenant"], value["email"]).get(connection_id)
    if not row:
        raise HTTPException(404, "Conexión Loyverse no disponible para este usuario y catálogo.")
    if row["status"] != "connected":
        raise HTTPException(409, "Prueba de nuevo la conexión antes de continuar.")
    if store_id is not None and store_id not in {s["id"] for s in row["stores"]}:
        raise HTTPException(422, "La sucursal no pertenece a la conexión elegida.")
    return deepcopy(row)


def save(db, value, tested, name, store_id, connection_id):
    tenant, actor = value["platform_tenant"], value["email"]
    rows = connections(db, tenant, actor, lock=True)
    if connection_id and connection_id not in rows:
        raise HTTPException(404, "Conexión no disponible.")
    if store_id not in {s["id"] for s in tested["stores"]}:
        raise HTTPException(422, "Selecciona una sucursal de la cuenta probada.")
    if not connection_id and len(rows) >= 20:
        raise HTTPException(422, "Límite de veinte conexiones por usuario y catálogo.")
    from .models import uid
    connection_id = connection_id or uid()
    old = rows.get(connection_id)
    if old and old["merchant_id"] != tested["merchant_id"]:
        raise HTTPException(409, "Para otra cuenta Loyverse agrega una conexión nueva.")
    row = {**deepcopy(tested), "id": connection_id, "name": name.strip(),
           "default_store_id": store_id, "status": "connected", "checked_at": time.time(),
           "revision": (old or {}).get("revision", 0) + 1}
    rows[connection_id] = row
    put(db, tenant, actor, PROVIDER, rows)
    audit(db, tenant, actor, "loyverse.connection.saved", after={"connection": connection_id})
    return public_connection(row)


def remove(db, value, connection_id):
    tenant, actor = value["platform_tenant"], value["email"]
    rows = connections(db, tenant, actor, lock=True)
    if connection_id not in rows:
        raise HTTPException(404, "Conexión no disponible.")
    del rows[connection_id]
    put(db, tenant, actor, PROVIDER, rows)
    jobs = db.scalars(select(GenerationJob).where(GenerationJob.tenant_id == tenant,
        GenerationJob.actor == actor, GenerationJob.kind == "loyverse_export").with_for_update()).all()
    for job in jobs:
        if job.payload.get("connection_id") != connection_id:
            continue
        if job.status == "paused":
            job.status = "queued"
        request_cancel(job)
        credentials = account(db, tenant, job.id, JOB_PROVIDER)
        if credentials:
            credentials.encrypted_credentials, credentials.status = seal({}), "disconnected"
    audit(db, tenant, actor, "loyverse.connection.deleted", after={"connection": connection_id})


def job_credentials(db, job):
    selected(db, {"platform_tenant": job["tenant_id"], "email": job["actor"]},
             job["payload"]["connection_id"], job["payload"]["store_id"])
    record = account(db, job["tenant_id"], job["id"], JOB_PROVIDER)
    if not record or record.status != "connected":
        raise ValueError("Las credenciales de esta carga fueron retiradas.")
    result = unseal(record.encrypted_credentials)
    if result.get("merchant_id") != job["payload"]["merchant_id"]:
        raise ValueError("La cuenta de esta carga no coincide con su conexión original.")
    return result
