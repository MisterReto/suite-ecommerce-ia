"""Durable capture-image jobs; the accepted image functions stay in studio_api."""
# Persistencia y recuperación de trabajos de captura que reutilizan el generador aceptado.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select, func
from .accounts import account, persist
from .catalog import audit
from .database import configured, transaction
from .models import GenerationJob, uid
from .security import require_role, member
from . import queue


# Selecciona la orquestación durable cuando STUDIO_IMAGE_JOBS=worker y existe SQL.
def enabled():
    return os.getenv("STUDIO_IMAGE_JOBS", "local") == "worker"


# Obtiene la carpeta autorizada de la captura que identifica el tenant del trabajo.
def tenant_for(value):
    root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root:
        raise HTTPException(503, "Selecciona la carpeta de trabajo antes de generar.")
    value["platform_tenant"] = root
    return root


# Traduce el job SQL al contrato compatible de captura sin exponer conexión cifrada.
def public_job(job):
    return {"id": job.id, "status": "running" if job.status == "processing" else job.status,
            "label": "Generando imágenes", "progress": job.progress, "message": job.message}


# Busca el trabajo activo del actor, incluyendo Deteniendo, para evitar duplicar una
# operación.
def find_active(value):
    if not enabled() or not configured():
        return None
    root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root:
        return None
    with transaction() as db:
        job = db.scalar(select(GenerationJob).where(
            GenerationJob.tenant_id == root, GenerationJob.actor == value.get("email", ""),
            GenerationJob.kind == "studio_generation", GenerationJob.status.in_(["queued", "processing", "cancelling"]))
            .order_by(GenerationJob.created_at.desc()).limit(1))
        return public_job(job) if job else None


# Lee el consumo ya registrado de la generación para comparar el incremento del trabajo.
def recorded_usage(value):
    if not configured() or not member(value.get("email", "")):
        return {}
    root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root:
        return {}
    keys = ("count", "cache_hits", "input_tokens", "output_tokens", "thinking_tokens")
    with transaction() as db:
        # SQL aggregates five numbers; never load all job payloads into API RAM.
        row = db.execute(select(*[
            func.coalesce(func.sum(GenerationJob.payload["usage"][key].as_integer()), 0).label(key)
            for key in keys
        ]).where(GenerationJob.tenant_id == root,
                 GenerationJob.actor == value.get("email", ""))).one()
        return dict(row._mapping)


# Valida confirmación/snapshot, guarda referencias y encola una captura o corrección
# idempotente.
def enqueue_capture(value, current, slots, data, corrections=()):
    from drive_service import DriveService
    from studio_api import runtime, file_path
    from creative_pipeline import IMAGE_MODEL
    from .api import image_unit, guard_cost
    from .worker import candidate_folder

    if not configured() or os.getenv("GENERATION_QUEUE_BACKEND") != "rq":
        raise HTTPException(503, "La generación separada requiere PostgreSQL, Redis y worker.")
    require_role(value, "admin", "editor")
    if not data.request_key or not data.confirm_cost:
        raise HTTPException(422, "Confirma el consumo y envía request_key para evitar duplicados.")
    tenant, actor = tenant_for(value), value["email"]
    unit = image_unit(IMAGE_MODEL)
    cost = len(slots) * unit if unit is not None else None
    guard_cost(cost)
    fingerprint = hashlib.sha256(json.dumps({"revision": current["revision"],
        "product": current["product"], "slots": slots, "corrections": list(corrections),
        "review": data.automatic_review}, sort_keys=True).encode()).hexdigest()
    with transaction() as db:
        queue.request_lock(db, tenant, data.request_key)
        queue.request_lock(db, tenant, "capture-active:" + actor)
        previous = db.scalar(select(GenerationJob).where(
            GenerationJob.tenant_id == tenant, GenerationJob.actor == actor,
            GenerationJob.request_key == data.request_key))
        if previous:
            if previous.payload.get("fingerprint") != fingerprint:
                raise HTTPException(409, "request_key ya se usó para otra solicitud.")
            return {"job": public_job(previous), "replayed": True}
        if find_active(value):
            raise HTTPException(409, "Espera a que termine tu generación actual.")
        if not queue.available(db):
            raise HTTPException(503, "No hay worker/Redis disponible; no se generó ni cobró ninguna imagen.")
        drive = DriveService.for_session(runtime, value)
        if drive.root_id != tenant:
            raise HTTPException(403, "La carpeta de la conexión no coincide.")
        job_id = uid()
        folder = candidate_folder(drive, job_id)
        references = [drive.upload(path, f"reference_{i}.jpg", folder, {"job_id": job_id})["id"]
                      for i, path in enumerate(current["references"])]
        prior = {}
        # These files let a new API session recover the previous image as well
        # as a completed candidate after a restart. No /tmp paths enter SQL.
        for slot, item in current["images"].items():
            prior[slot] = {key: deepcopy(item.get(key)) for key in ("history", "qa", "approved", "message")}
            for key in ("id", "raw_id"):
                prior[slot][key] = drive.upload(file_path(value, item[key]),
                    "previous_" + slot + ("_raw" if key == "raw_id" else "") + ".jpg", folder,
                    {"job_id": job_id, "kind": "previous"})["id"]
        payload = {"capture": {key: deepcopy(current[key]) for key in ("revision", "context", "product")},
                   "references": references, "previous": prior, "slots": slots,
                   "corrections": list(corrections), "automatic_review": data.automatic_review,
                   "brief": deepcopy(current.get("brief")), "completed_keys": [],
                   "results": {}, "fingerprint": fingerprint}
        job = GenerationJob(id=job_id, tenant_id=tenant, actor=actor,
                            kind="studio_generation", request_key=data.request_key,
                            model=IMAGE_MODEL, estimated_cost=cost, payload=payload)
        persist(db, tenant, actor, value)
        db.add(job)
        queue.dispatch(db, job)
        audit(db, tenant, actor, "capture.generation.queued",
              after={"job_id": job.id, "sku": current["product"]["sku"], "revision": current["revision"]})
        return {"job": public_job(job), "status": "queued", "job_id": job.id}


# Ejecuta la captura durable con el generador existente, checkpoints y persistencia de cada
# candidato.
def process_capture(job, value, drive, owner):
    from studio_api import runtime, asset, file_path
    from creative_pipeline import IMAGE_MODEL, plan_key, load_style_examples
    from image_generation_service import ImageGenerationService
    from .worker import download_reference, file_checksum, candidate_folder
    from PIL import Image

    if job["model"] != IMAGE_MODEL:
        raise ValueError("El modelo cambió después de confirmar; no se generó ninguna imagen.")
    payload = deepcopy(job["payload"])
    current = {**payload["capture"], "references": [], "images": {}}
    value["capture_revision"] = current["revision"]
    for index, file_id in enumerate(payload["references"]):
        current["references"].append(download_reference(drive, file_id,
            f"/tmp/{value['file_namespace']}_reference_{index}.jpg"))
    if payload["corrections"]:
        for slot in payload["slots"]:
            prior = payload["previous"][slot]
            path = download_reference(drive, prior["raw_id"], f"/tmp/{value['file_namespace']}_previous_{slot}.jpg")
            current["images"][slot] = {"raw_id": asset(value, path), "history": prior.get("history") or []}
    service = ImageGenerationService()
    if any(slot != "1_hd" for slot in payload["slots"]):
        if payload.get("brief"):
            styles, _ = load_style_examples(runtime, value)
            current.update(brief=payload["brief"], brief_key=plan_key(current["product"], styles))
        payload["in_flight"] = {"operation": "creative_plan"}
        queue.checkpoint(job["id"], owner, payload=payload)
        plan, styles = service.plan(value, current,
            lambda progress, message: queue.checkpoint(job["id"], owner, progress=progress, message=message))
        payload.update(brief=plan, in_flight=None)
        queue.checkpoint(job["id"], owner, payload=payload)
    else:
        plan, styles = {}, []
    folder = candidate_folder(drive, job["id"])
    for slot in payload["slots"]:
        if slot in payload["completed_keys"]:
            continue
        payload["in_flight"] = {"operation": "image_generation", "slot": slot}
        queue.checkpoint(job["id"], owner, payload=payload, message="Generando " + slot)
        prompt = runtime.PROMPT_HD if slot == "1_hd" else plan["lifestyle" if slot == "2_uso" else "comercial"]
        item = service.generate(value, current, slot, prompt, styles,
            feedback=payload["corrections"], automatic_review=payload["automatic_review"])
        output, raw = file_path(value, item["id"]), file_path(value, item["raw_id"])
        with Image.open(output) as picture:
            width, height = picture.size
        prefix = current["product"]["sku"] + "_" + slot
        uploaded = drive.upload(output, prefix + ".jpg", folder, {"job_id": job["id"], "slot": slot})
        raw_file = drive.upload(raw, prefix + "_raw.jpg", folder, {"job_id": job["id"], "kind": "raw"})
        payload["results"][slot] = {"id": uploaded["id"], "raw_id": raw_file["id"],
            "filename": prefix + ".jpg", "checksum": file_checksum(output),
            "width": width, "height": height, "history": item["history"], "qa": item.get("qa"),
            "approved": False, "message": item["message"]}
        payload["completed_keys"].append(slot)
        payload["in_flight"] = None
        queue.checkpoint(job["id"], owner, payload=deepcopy(payload),
                         progress=int(len(payload["completed_keys"]) * 100 / len(payload["slots"])))
        with transaction() as db:
            audit(db, job["tenant_id"], job["actor"], "capture.image.generated",
                  after={"job_id": job["id"], "sku": current["product"]["sku"], "slot": slot})
        for key in (item["id"], item["raw_id"]):
            Path(value["studio_files"].pop(key)).unlink(missing_ok=True)
        current["images"].pop(slot, None)
    return True


# Reconstruye el borrador y los candidatos de un trabajo con referencias Drive.
def restore(value, payload, job_id):
    from studio_api import runtime, asset
    from drive_service import DriveService
    from .worker import download_reference

    current = value.get("studio_draft")
    if current and current["revision"] != payload["capture"]["revision"]:
        return  # Do not attach another product's images to a new capture.
    drive = DriveService.for_session(runtime, value)
    if not current:
        paths = [download_reference(drive, file_id, f"/tmp/{value['file_namespace']}_restore_ref_{index}.jpg")
                 for index, file_id in enumerate(payload["references"])]
        current = {**deepcopy(payload["capture"]), "references": paths, "images": {},
                   "front_id": asset(value, paths[0]), "back_id": asset(value, paths[1]) if len(paths) > 1 else None}
        value["studio_draft"] = current
        value["capture_revision"] = current["revision"]
    current["brief"] = deepcopy(payload.get("brief"))
    loaded = value.setdefault("studio_loaded_results", {})
    entries = {**payload.get("previous", {}), **payload.get("results", {})}
    for slot, item in entries.items():
        marker = job_id + ":" + slot + ":" + item["id"]
        if marker in loaded:
            continue
        restored = {key: deepcopy(item.get(key)) for key in ("history", "qa", "approved", "message")}
        for key in ("id", "raw_id"):
            path = download_reference(drive, item[key],
                f"/tmp/{value['file_namespace']}_restore_{job_id}_{slot}_{key}.jpg")
            restored[key] = asset(value, path)
        current["images"][slot] = restored
        value.setdefault("studio_asset_jobs", {})[slot] = job_id
        runtime.captura.stage_image(value, current["product"]["sku"], slot,
                                   value["studio_files"][restored["id"]], current["revision"])
        loaded[marker] = True


# Consulta un trabajo autorizado y recupera sus resultados para la interfaz de captura.
def get_job(value, job_id):
    from studio_api import view

    require_role(value, "admin", "editor", "viewer")
    with transaction() as db:
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id,
            GenerationJob.tenant_id == tenant_for(value), GenerationJob.actor == value.get("email", ""),
            GenerationJob.kind == "studio_generation"))
        if not job:
            raise HTTPException(404, "Trabajo no disponible.")
        public, payload = public_job(job), deepcopy(job.payload)
    if payload.get("results") or public["status"] in {"completed", "failed", "cancelled"}:
        restore(value, payload, job_id)
    return {"job": public, "draft": view(value)}


# Recupera el último trabajo propio después de iniciar una sesión nueva.
def recover_latest(value):
    if not configured() or not member(value.get("email", "")):
        return
    root = tenant_for(value)
    with transaction() as db:
        record = account(db, root, value["email"], "capture_draft")
        if record and record.status != "connected":
            return  # Clearing the durable draft also disables legacy job recovery.
        current = value.get("studio_draft")
        query = select(GenerationJob).where(GenerationJob.tenant_id == root,
            GenerationJob.actor == value.get("email", ""), GenerationJob.kind == "studio_generation")
        if current:
            query = query.where(GenerationJob.payload["capture"]["revision"].as_string() == current["revision"])
        elif record:
            return  # A persisted capture is authoritative over an unrelated old job.
        job = db.scalar(query.order_by(GenerationJob.created_at.desc()).limit(1))
        if job:
            payload, job_id = deepcopy(job.payload), job.id
        else:
            return
    restore(value, payload, job_id)


# Marca el trabajo como guardado para no recuperarlo como un borrador pendiente.
def record_saved(value, current):
    """Remember the existing capture save; never repeat a Sheet write on recovery."""
    from .capture_bridge import mark_saved

    with transaction() as db:
        jobs = db.scalars(select(GenerationJob).where(
            GenerationJob.tenant_id == tenant_for(value),
            GenerationJob.actor == value.get("email", ""),
            GenerationJob.kind == "studio_generation",
            GenerationJob.payload["capture"]["revision"].as_string() == current["revision"]
        ).with_for_update())
        for job in jobs:
            payload = deepcopy(job.payload)
            payload["capture"]["saved"] = current["saved"]
            job.payload = payload
        mark_saved(db, value, current)
        audit(db, tenant_for(value), value["email"], "capture.saved",
              after={"sku": current["product"]["sku"], "revision": current["revision"]})


# Persiste aprobación/rechazo de un slot conservando el estado de una cancelación.
def record_approval(value, slot, approved):
    job_id = value.get("studio_asset_jobs", {}).get(slot)
    if not job_id:
        return
    with transaction() as db:
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id,
            GenerationJob.tenant_id == tenant_for(value), GenerationJob.actor == value.get("email", "")).with_for_update())
        if not job or slot not in job.payload.get("results", {}):
            return
        payload = deepcopy(job.payload)
        payload["results"][slot]["approved"] = approved
        job.payload = payload
        if job.status in {"completed", "approved", "rejected"}:
            states = [item.get("approved") for item in payload["results"].values()]
            job.status = "approved" if all(states) else "completed"
        audit(db, job.tenant_id, job.actor, "capture.image.reviewed",
              after={"job_id": job_id, "slot": slot, "approved": approved})
