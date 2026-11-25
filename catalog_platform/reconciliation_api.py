"""Administrator-only reconciliation requests and paginated preview/results."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import queue
from .api import admin, context
from .catalog import audit
from .database import transaction
from .models import AuditLog, GenerationJob, uid
from .woocommerce_export import connection_status, store_url
from .woocommerce_reconciliation import KIND, read_page, result_view

router = APIRouter(prefix="/reconciliation")
ACTIVE = ("queued","processing","cancelling")


class Approval(BaseModel):
    confirm: bool
    all: bool = False
    keys: list[str] = Field(default_factory=list,max_length=500)


def scoped(value):
    return select(GenerationJob).where(GenerationJob.tenant_id==value["platform_tenant"],
        GenerationJob.kind==KIND,GenerationJob.payload["store"].as_string()==store_url())


def describe(job):
    return {"id":job.id,"status":job.status,"progress":job.progress,"message":job.message,
            "mode":"apply" if job.payload.get("preview") else "preview",
            "counts":job.payload.get("counts",{}),"pages":job.payload.get("pages",0),
            "finished_at":job.finished_at}


def find(db,value,job_id):
    job = db.scalar(scoped(value).where(GenerationJob.id==job_id))
    if not job:
        raise HTTPException(404,"No se encontró esta sincronización.")
    return job


def enqueue(value,preview=None,approval=None):
    admin(value)
    if not connection_status()["configured"]:
        raise HTTPException(503,"Configura la conexión de WooCommerce.")
    tenant,origin = value["platform_tenant"],store_url()
    with transaction() as db:
        queue.request_lock(db,"woocommerce",origin+":reconcile")
        active = db.scalar(select(GenerationJob).where(GenerationJob.kind==KIND,
            GenerationJob.payload["store"].as_string()==origin,GenerationJob.status.in_(ACTIVE)).limit(1))
        if active:
            if active.tenant_id==tenant and not preview and not active.payload.get("preview"):
                return describe(active)
            raise HTTPException(409,"Ya hay una sincronización en curso para esta tienda.")
        payload = {"store":origin}
        if preview:
            source = find(db,value,preview)
            if source.status!="completed" or source.payload.get("preview"):
                raise HTTPException(409,"Se requiere una vista previa terminada.")
            if not approval.confirm or (approval.all == bool(approval.keys)):
                raise HTTPException(422,"Confirma la selección o todos los cambios elegibles.")
            payload.update(preview=preview,pages=source.payload["pages"],all=approval.all,keys=sorted(set(approval.keys)))
            previous = db.scalar(scoped(value).where(GenerationJob.payload["preview"].as_string()==preview)
                                 .order_by(GenerationJob.created_at.desc()).limit(1))
            if previous:
                if all(previous.payload.get(k)==payload[k] for k in ("all","keys")):
                    return describe(previous)
                raise HTTPException(409,"Esta vista previa ya se utilizó. Genera otra.")
        if not queue.available(db):
            raise HTTPException(503,"El worker no está disponible.")
        job = GenerationJob(tenant_id=tenant,actor=value["email"],kind=KIND,provider="woocommerce",
                            request_key=uid(),payload=payload,message="En cola para conciliar el catálogo")
        db.add(job)
        queue.dispatch(db,job)
        audit(db,tenant,value["email"],"woocommerce.reconcile.queued",
              after={"job":job.id,"preview":preview,"selection":payload.get("keys"),"all":payload.get("all")})
        return describe(job)


@router.post("",status_code=202)
def preview(value=Depends(context)):
    return enqueue(value)


@router.get("")
def latest(value=Depends(context)):
    admin(value)
    with transaction() as db:
        job = db.scalar(scoped(value).order_by(GenerationJob.created_at.desc()).limit(1))
        last = db.scalar(scoped(value).with_only_columns(GenerationJob.finished_at).where(
            GenerationJob.status=="completed",GenerationJob.payload["preview"].as_string().is_not(None))
            .order_by(GenerationJob.finished_at.desc()).limit(1))
        return {"job":describe(job) if job else None,"last_sync":last}


@router.post("/{job_id}/apply",status_code=202)
def apply(job_id:str, data:Approval, value=Depends(context)):
    return enqueue(value,job_id,data)


@router.post("/{job_id}/cancel")
def cancel(job_id:str,value=Depends(context)):
    admin(value)
    with transaction() as db:
        job = db.scalar(scoped(value).where(GenerationJob.id==job_id).with_for_update())
        if not job:
            raise HTTPException(404,"Sincronización no disponible.")
        queue.request_cancel(job)
        return describe(job)


@router.get("/{job_id}")
def details(job_id:str,page:int=Query(0,ge=0,le=10000),value=Depends(context)):
    admin(value)
    with transaction() as db:
        job = find(db,value,job_id)
        summary = describe(job)
        if job.payload.get("preview"):
            rows = db.execute(select(AuditLog.after,AuditLog.result).where(AuditLog.tenant_id==job.tenant_id,
                AuditLog.action=="woocommerce.reconcile.item",AuditLog.after["job"].as_string()==job_id)
                .order_by(AuditLog.created_at,AuditLog.id).offset(page*50).limit(51)).all()
            return {**summary,"rows":[{"sku":item["sku"],"category":item["category"],"outcome":outcome}
                                      for item,outcome in rows[:50]],"more":len(rows)>50}
    rows = []
    if summary["status"]=="completed" and page<summary["pages"]:
        try:
            rows = [result_view(row) for row in read_page(job_id,page)]
        except ValueError as exc:
            raise HTTPException(410,str(exc)) from None
    return {**summary,"rows":rows,"more":page+1<summary["pages"]}
