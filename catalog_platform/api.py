"""Authenticated catalog API. HTTP validates/enqueues; workers execute remote writes."""

from datetime import datetime, timezone
import hashlib
import io
import json
import os
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .database import configured, transaction
from .models import (
    Product,
    ProductImage,
    GenerationJob,
    GenerationBatch,
    GeneratedAsset,
    InventoryMovement,
    IntegrationAccount,
    AuditLog,
    SyncEvent,
    WorkerHeartbeat,
    uid,
)
from .security import require_role, role_for, cipher, member
from .catalog import serialize, product_for, save_product, audit, csv_export, move_stock
from .accounts import persist
from .queue import available, request_lock, dispatch

router = APIRouter(prefix="/api/platform")


def context(request: Request):
    from studio_api import runtime

    value = runtime._obtener_sesion(request)
    if not value:
        raise HTTPException(401, "Conecta Google Drive para continuar.")
    if not member(value.get("email", "")):
        raise HTTPException(
            403, "El administrador debe autorizar tu cuenta en APP_ROLE_MAP."
        )
    if not configured():
        raise HTTPException(
            503,
            "El catálogo maestro requiere configurar PostgreSQL; la captura actual sigue disponible.",
        )
    if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        value["carpeta_raiz_id_manual"] = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not value.get("gemini_key") and os.getenv("AI_API_KEY"):
        value["gemini_key"] = os.environ["AI_API_KEY"]
    if not value.get("platform_tenant"):
        from drive_service import DriveService

        chosen = value.get("carpeta_raiz_id_manual") or os.getenv(
            "GOOGLE_DRIVE_FOLDER_ID"
        )
        if chosen:
            service = runtime._get_drive_service(value)
            info = (
                service.files()
                .get(fileId=chosen, fields="id,mimeType,trashed")
                .execute()
            )
            if (
                info.get("trashed")
                or info.get("mimeType") != "application/vnd.google-apps.folder"
            ):
                raise HTTPException(403, "La carpeta configurada no está disponible.")
            value["platform_tenant"] = chosen
            value["carpeta_raiz_id_manual"] = chosen
        else:
            if role_for(value.get("email", "")) == "viewer":
                raise HTTPException(
                    503, "El administrador debe seleccionar la carpeta de trabajo."
                )
            service = DriveService.for_session(runtime, value)
            value["platform_tenant"] = service.root_id
    return value


def tenant(value):
    return value["platform_tenant"]


def actor(value):
    return value.get("email", "usuario")


def edit(value):
    require_role(value, "admin", "editor")


def admin(value):
    require_role(value, "admin")


class ProductInput(BaseModel):
    sku: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    barcode: str = Field(default="", max_length=40)
    name: str = Field(min_length=1, max_length=180)
    brand: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=160)
    subcategory: str = Field(default="", max_length=160)
    short_description: str = Field(default="", max_length=600)
    long_description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    attributes: dict = Field(default_factory=dict)
    product_type: str = Field(
        default="simple", pattern=r"^(simple|variable|variation)$"
    )
    parent_id: str | None = None
    price: float | None = Field(default=0, ge=0, le=1000000, allow_inf_nan=False)
    cost: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    stock: float | None = Field(default=0, ge=0, le=1000000, allow_inf_nan=False)
    version: int | None = None

    @field_validator("attributes")
    @classmethod
    def bounded_attributes(cls, value):
        if len(value) > 30:
            raise ValueError("Máximo 30 atributos.")
        for key, item in value.items():
            if len(key) > 80 or not isinstance(item, (str, list)):
                raise ValueError(
                    "Usa nombres cortos y valores de texto o listas de opciones."
                )
            values = item if isinstance(item, list) else [item]
            if len(values) > 50 or any(
                not isinstance(v, str) or len(v) > 160 for v in values
            ):
                raise ValueError("Opciones de atributo demasiado grandes.")
        return value

    @field_validator("tags")
    @classmethod
    def bounded_tags(cls, value):
        if any(len(tag) > 80 for tag in value):
            raise ValueError("Etiquetas demasiado largas.")
        return list(dict.fromkeys(value))


class BatchInput(BaseModel):
    product_ids: list[str] = Field(default_factory=list, max_length=300)
    category: str | None = Field(default=None, max_length=160)
    pending: bool = False
    slots: list[str] = Field(
        default_factory=lambda: ["1_hd", "2_uso", "3_comercial"],
        min_length=1,
        max_length=3,
    )
    quantity: int = Field(default=1, ge=1, le=4)
    quality: str = Field(default="native", pattern=r"^native$")
    automatic_review: bool = False


class EnqueueInput(BatchInput):
    request_key: str = Field(min_length=12, max_length=100)
    estimate_token: str = Field(min_length=64, max_length=64)
    confirm: bool


class ReviewInput(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    role: str = Field(
        default="gallery", pattern=r"^(main|gallery|lifestyle|commercial)$"
    )


class CorrectionInput(BaseModel):
    feedback: str = Field(min_length=1, max_length=600)
    confirm_cost: bool
    request_key: str = Field(min_length=12, max_length=100)


class StockInput(BaseModel):
    quantity: float = Field(ge=0, le=1000000, allow_inf_nan=False)
    event_id: str = Field(min_length=12, max_length=200)
    version: int
    reason: str = Field(min_length=3, max_length=300)


@router.get("/status")
def status(request: Request):
    from studio_api import runtime

    value = runtime._obtener_sesion(request)
    result = {
        "configured": configured(),
        "ready": False,
        "worker_ready": False,
        "authenticated": bool(value),
        "role": role_for(value.get("email", "")) if value else "viewer",
    }
    if not configured():
        return {**result, "message": "PostgreSQL y worker pendientes de configuración."}
    try:
        cipher()
        with transaction() as db:
            db.scalar(select(Product.id).limit(1))
            result.update(
                ready=True, worker_ready=available(db), message="Catálogo preparado."
            )
    except Exception:
        result["message"] = (
            "Revisa DATABASE_URL, el esquema y CREDENTIAL_ENCRYPTION_KEY del servidor."
        )
    return result


@router.get("/products")
def products(
    q: str = "",
    filter: str = "all",
    offset: int = 0,
    limit: int = 50,
    value=Depends(context),
):
    with transaction() as db:
        query = select(Product).where(Product.tenant_id == tenant(value))
        if q:
            pattern = "%" + q[:180].replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(
                or_(
                    Product.name.ilike(pattern, escape="\\"),
                    Product.sku.ilike(pattern, escape="\\"),
                    Product.barcode.ilike(pattern, escape="\\"),
                )
            )
        filters = {
            "published": Product.status == "published",
            "pending": Product.status == "pending",
            "error": Product.sync_status == "error",
            "out": Product.stock == 0,
            "low": Product.stock.between(1, 5),
            "difference": Product.stock != Product.woocommerce_stock,
        }
        if filter in filters:
            query = query.where(filters[filter])
        count = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(
            query.order_by(Product.updated_at.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 100)))
        ).all()
        items = []
        for product in rows:
            image = db.scalar(
                select(ProductImage)
                .where(
                    ProductImage.product_id == product.id,
                    ProductImage.tenant_id == tenant(value),
                    ProductImage.status.in_(["approved", "published"]),
                )
                .order_by(ProductImage.created_at)
            )
            items.append(
                {
                    **serialize(product),
                    "internal_product_id": product.id,
                    "image_id": image.id if image else None,
                }
            )
        return {"items": items, "total": count}


@router.post("/products", status_code=201)
def create_product(data: ProductInput, value=Depends(context)):
    edit(value)
    try:
        with transaction() as db:
            return {
                "product": serialize(
                    save_product(
                        db,
                        tenant(value),
                        actor(value),
                        data.model_dump(exclude={"version"}),
                    )
                )
            }
    except IntegrityError:
        raise HTTPException(409, "El SKU ya existe en el catálogo.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/products/{product_id}")
def get_product(product_id: str, value=Depends(context)):
    with transaction() as db:
        product = product_for(db, tenant(value), product_id)

        def related(model):
            return [
                serialize(row)
                for row in db.scalars(
                    select(model)
                    .where(
                        model.tenant_id == tenant(value), model.product_id == product.id
                    )
                    .order_by(model.created_at.desc())
                    .limit(50)
                )
            ]

        return {
            "product": {**serialize(product), "internal_product_id": product.id},
            "images": related(ProductImage),
            "assets": related(GeneratedAsset),
            "jobs": related(GenerationJob),
            "movements": related(InventoryMovement),
            "sync_events": related(SyncEvent),
            "variants": [
                serialize(p)
                for p in db.scalars(
                    select(Product).where(
                        Product.tenant_id == tenant(value),
                        Product.parent_id == product.id,
                    )
                )
            ],
        }


@router.put("/products/{product_id}")
def update_product(product_id: str, data: ProductInput, value=Depends(context)):
    edit(value)
    try:
        with transaction() as db:
            result = save_product(
                db,
                tenant(value),
                actor(value),
                data.model_dump(exclude={"version"}),
                product_id,
                data.version,
            )
            return {"product": serialize(result)}
    except IntegrityError:
        raise HTTPException(409, "Ese SKU ya pertenece a otro producto.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/products/{product_id}/stock")
def inventory_change(product_id: str, data: StockInput, value=Depends(context)):
    edit(value)
    if os.getenv("STOCK_AUTHORITY", "app") == "loyverse":
        raise HTTPException(
            409, "Loyverse es la autoridad física. Registra el movimiento en POS."
        )
    with transaction() as db:
        product = product_for(db, tenant(value), product_id, True)
        existing = db.scalar(
            select(InventoryMovement).where(
                InventoryMovement.product_id == product_id,
                InventoryMovement.tenant_id == tenant(value),
                InventoryMovement.source == "app",
                InventoryMovement.source_event_id == data.event_id,
            )
        )
        if existing:
            return {"movement": serialize(existing)}
        if data.version != product.version:
            raise HTTPException(409, "El stock cambió. Recarga antes de registrar.")
        if db.scalar(
            select(GenerationJob.id).where(
                GenerationJob.product_id == product_id,
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.kind.in_(["publication", "stock_sync"]),
                GenerationJob.status.in_(["queued", "processing"]),
            )
        ):
            raise HTTPException(
                409, "Hay una escritura a la tienda en curso. Espera su resultado."
            )
        movement = move_stock(
            db,
            product,
            data.quantity,
            "app",
            data.event_id,
            actor(value),
            {"reason": data.reason},
        )
        db.flush()
        return {"movement": serialize(movement)}


class ReferenceInput(BaseModel):
    upload_id: str = Field(max_length=64)


@router.post("/products/{product_id}/reference")
def reference(product_id: str, data: ReferenceInput, value=Depends(context)):
    edit(value)
    from studio_api import file_path, runtime
    from drive_service import DriveService
    from PIL import Image

    path = file_path(value, data.upload_id)
    with transaction() as db:
        product = serialize(product_for(db, tenant(value), product_id))
    service = DriveService.for_session(runtime, value)
    folder = service.working_folder("images", "originals")
    raw = open(path, "rb").read()
    checksum = hashlib.sha256(raw).hexdigest()
    with transaction() as db:
        existing = db.scalar(
            select(ProductImage).where(
                ProductImage.tenant_id == tenant(value),
                ProductImage.product_id == product_id,
                ProductImage.role == "reference",
                ProductImage.checksum == checksum,
            )
        )
        if existing:
            return {"image": serialize(existing)}
    stored = service.upload(
        path, f"{product['sku']}_original_{secrets.token_hex(8)}.jpg", folder
    )
    with Image.open(path) as picture:
        width, height = picture.size
    with transaction() as db:
        item = ProductImage(
            tenant_id=tenant(value),
            product_id=product_id,
            drive_file_id=stored["id"],
            role="reference",
            status="approved",
            checksum=checksum,
            width=width,
            height=height,
        )
        db.add(item)
        audit(
            db,
            tenant(value),
            actor(value),
            "reference.added",
            product_id,
            after={"file_id": stored["id"], "checksum": checksum},
        )
        db.flush()
        return {"image": serialize(item)}


@router.get("/images/{image_id}")
def image(image_id: str, download: bool = False, value=Depends(context)):
    from studio_api import runtime
    from drive_service import DriveService

    with transaction() as db:
        item = db.scalar(
            select(ProductImage).where(
                ProductImage.id == image_id, ProductImage.tenant_id == tenant(value)
            )
        )
        if not item:
            raise HTTPException(404, "Imagen no disponible.")
        file_id = item.drive_file_id
    data = DriveService.for_session(runtime, value).download(file_id)
    # Metadata is authenticated and scoped to this tenant.
    return Response(
        data,
        media_type=item.mime_type,
        headers={
            "Cache-Control": "no-store",
            **(
                {"Content-Disposition": "attachment; filename=imagen-rincon"}
                if download
                else {}
            ),
        },
    )


def selection(db, value, data, lock=False):
    from creative_pipeline import SLOTS

    if len(set(data.slots)) != len(data.slots) or any(
        slot not in SLOTS for slot in data.slots
    ):
        raise HTTPException(422, "Tipos de imagen inválidos.")
    query = select(Product).where(
        Product.tenant_id == tenant(value), Product.product_type != "variable"
    )
    if data.product_ids:
        query = query.where(Product.id.in_(list(set(data.product_ids))))
    elif data.category:
        query = query.where(Product.category == data.category)
    elif data.pending:
        query = query.where(Product.status == "pending")
    else:
        raise HTTPException(422, "Selecciona productos, una categoría o pendientes.")
    query = query.order_by(Product.id)
    if lock:
        query = query.with_for_update()
    rows = db.scalars(query).all()
    if not rows or data.product_ids and len(rows) != len(set(data.product_ids)):
        raise HTTPException(422, "La selección incluye productos no disponibles.")
    count = len(rows) * len(data.slots) * data.quantity
    if count > int(os.getenv("MAX_IMAGES_PER_BATCH", os.getenv("MAX_BATCH_IMAGES", "300"))):
        raise HTTPException(
            422, "El lote supera el límite de imágenes. Divide la selección."
        )
    missing = []
    references = {}
    for product in rows:
        refs = db.scalars(
            select(ProductImage)
            .where(
                ProductImage.tenant_id == tenant(value),
                ProductImage.product_id == product.id,
                ProductImage.role == "reference",
                ProductImage.status == "approved",
            )
            .order_by(ProductImage.created_at)
            .limit(2)
        ).all()
        if not refs:
            missing.append(product.sku)
        references[product.id] = [item.drive_file_id for item in refs]
    if missing:
        raise HTTPException(
            422, "Sube una foto de referencia para: " + ", ".join(missing[:12])
        )
    return rows, references, count


def image_unit(model):
    import math

    configured = os.getenv("AI_ESTIMATED_IMAGE_USD")
    if not configured and model != "gemini-3.1-flash-image":
        return None
    try:
        value = float(configured or "0.067")
    except ValueError:
        raise RuntimeError(
            "AI_ESTIMATED_IMAGE_USD debe ser una tarifa válida."
        ) from None
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise RuntimeError("AI_ESTIMATED_IMAGE_USD fuera de rango.")
    return value


def estimate(db, value, data, lock=False):
    from creative_pipeline import IMAGE_MODEL

    rows, refs, count = selection(db, value, data, lock)
    unit = image_unit(IMAGE_MODEL)
    guard_cost(count * unit if unit is not None else None)
    contract = {
        "products": [(p.id, p.version) for p in rows],
        "references": refs,
        "slots": data.slots,
        "quantity": data.quantity,
        "review": data.automatic_review,
        "model": IMAGE_MODEL,
        "unit": unit,
    }
    token = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    return (
        {
            "products": len(rows),
            "images": count,
            "provider": "gemini",
            "model": IMAGE_MODEL,
            "estimated_usd": round(count * unit, 4) if unit is not None else None,
            "estimate_token": token,
            "note": "Estimación de imágenes 1K; investigación, entradas y revisión añaden consumo variable. La tarifa real corresponde a tu proyecto.",
        },
        rows,
        refs,
    )


def guard_cost(cost):
    import math

    configured = os.getenv("MAX_ESTIMATED_BATCH_COST", "")
    if not configured:
        return
    try:
        maximum = float(configured)
    except ValueError:
        raise RuntimeError("MAX_ESTIMATED_BATCH_COST debe ser un importe en USD.") from None
    if not math.isfinite(maximum) or maximum < 0:
        raise RuntimeError("MAX_ESTIMATED_BATCH_COST debe ser finito y no negativo.")
    if cost is None or cost > maximum:
        raise HTTPException(422, "El costo estimado supera el límite configurado o no está disponible.")


@router.post("/generation/estimate")
def generation_estimate(data: BatchInput, value=Depends(context)):
    edit(value)
    with transaction() as db:
        return estimate(db, value, data)[0]


@router.post("/generation/jobs", status_code=202)
def enqueue(data: EnqueueInput, value=Depends(context)):
    edit(value)
    if not data.confirm:
        raise HTTPException(
            422, "Revisa el lote y confirma el costo antes de ejecutar."
        )
    if not value.get("gemini_key"):
        raise HTTPException(422, "Conecta tu clave de IA en Más → Conexiones.")
    with transaction() as db:
        request_lock(db, tenant(value), data.request_key)
        old = db.scalars(
            select(GenerationJob).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.request_key == data.request_key,
            )
        ).all()
        if old:
            if any(job.kind != "generation" or job.actor != actor(value)
                   or job.payload.get("slots") != data.slots
                   or job.payload.get("quantity") != data.quantity
                   or bool(job.payload.get("automatic_review")) != data.automatic_review for job in old):
                raise HTTPException(409, "request_key ya corresponde a otra solicitud.")
            if data.product_ids and set(data.product_ids) != {job.product_id for job in old}:
                raise HTTPException(409, "request_key ya corresponde a otros productos.")
            return {"batch_id": old[0].batch_id, "jobs": [serialize(job) for job in old], "replayed": True}
        quoted, rows, references = estimate(db, value, data, True)
        if quoted["estimate_token"] != data.estimate_token:
            raise HTTPException(409, "El lote cambió. Consulta la estimación otra vez.")
        if not available(db):
            raise HTTPException(
                503, "No hay worker conectado. No se aceptó ni cobró el lote."
            )
        persist(db, tenant(value), actor(value), value)
        batch = GenerationBatch(
            tenant_id=tenant(value), actor=actor(value), request_key=data.request_key,
            product_count=len(rows), image_count=quoted["images"],
            estimated_cost=quoted["estimated_usd"],
        )
        db.add(batch)
        db.flush()
        jobs = []
        for product in rows:
            if db.scalar(
                select(GenerationJob.id).where(
                    GenerationJob.product_id == product.id,
                    GenerationJob.tenant_id == tenant(value),
                    GenerationJob.status.in_(["queued", "processing"]),
                )
            ):
                raise HTTPException(409, f"{product.sku} ya tiene un trabajo activo.")
            payload = {
                "product": serialize(product),
                "references": references[product.id],
                "slots": data.slots,
                "quantity": data.quantity,
                "automatic_review": data.automatic_review,
                "completed_keys": [],
                "estimate_token": data.estimate_token,
            }
            job = GenerationJob(
                tenant_id=tenant(value),
                product_id=product.id,
                batch_id=batch.id,
                actor=actor(value),
                request_key=data.request_key,
                payload=payload,
                model=quoted["model"],
                estimated_cost=(
                    quoted["estimated_usd"] / len(rows)
                    if quoted["estimated_usd"] is not None
                    else None
                ),
            )
            db.add(job)
            db.flush()
            dispatch(db, job)
            jobs.append(serialize(job))
            audit(
                db,
                tenant(value),
                actor(value),
                "generation.queued",
                product.id,
                after={"job_id": job.id, "estimated_cost": job.estimated_cost},
            )
        return {"batch_id": batch.id, "status": "queued", "jobs": jobs}


@router.get("/generation/batches")
def batches(value=Depends(context)):
    with transaction() as db:
        records = db.scalars(select(GenerationBatch)
                             .where(GenerationBatch.tenant_id == tenant(value))
                             .order_by(GenerationBatch.created_at.desc()).limit(50)).all()
        result = []
        for batch in records:
            states = dict(db.execute(select(GenerationJob.status, func.count())
                                     .where(GenerationJob.batch_id == batch.id)
                                     .group_by(GenerationJob.status)).all())
            result.append({**serialize(batch), "job_states": states})
        return {"items": result}


@router.get("/jobs")
def jobs(value=Depends(context)):
    with transaction() as db:
        return {
            "items": [
                serialize(job)
                for job in db.scalars(
                    select(GenerationJob)
                    .where(GenerationJob.tenant_id == tenant(value))
                    .order_by(GenerationJob.created_at.desc())
                    .limit(100)
                )
            ]
        }


@router.get("/assets")
def assets(value=Depends(context)):
    with transaction() as db:
        rows = db.execute(
            select(GeneratedAsset, Product)
            .join(Product, Product.id == GeneratedAsset.product_id)
            .where(GeneratedAsset.tenant_id == tenant(value))
            .order_by(GeneratedAsset.created_at.desc())
            .limit(100)
        ).all()
        return {
            "items": [
                {
                    **serialize(asset),
                    "product_name": p.name,
                    "sku": p.sku,
                    "estimated_correction_usd": image_unit(asset.model),
                }
                for asset, p in rows
            ]
        }


@router.post("/assets/{asset_id}/review")
def review(asset_id: str, data: ReviewInput, value=Depends(context)):
    edit(value)
    with transaction() as db:
        asset = db.scalar(
            select(GeneratedAsset)
            .where(
                GeneratedAsset.id == asset_id, GeneratedAsset.tenant_id == tenant(value)
            )
            .with_for_update()
        )
        if not asset:
            raise HTTPException(404, "Imagen no disponible.")
        product_for(db, tenant(value), asset.product_id, True)
        if asset.status == "published":
            raise HTTPException(
                409, "La imagen ya está publicada; genera una corrección nueva."
            )
        if db.scalar(
            select(GenerationJob.id).where(
                GenerationJob.product_id == asset.product_id,
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.kind == "publication",
                GenerationJob.status.in_(["queued", "processing"]),
            )
        ):
            raise HTTPException(
                409,
                "La publicación está en curso. Espera su resultado antes de cambiar la aprobación.",
            )
        image = db.get(ProductImage, asset.image_id)
        previous = asset.status
        asset.status = data.status
        image.status = data.status
        image.role = data.role
        if data.role == "main" and data.status == "approved":
            for other in db.scalars(
                select(ProductImage).where(
                    ProductImage.product_id == asset.product_id,
                    ProductImage.tenant_id == tenant(value),
                    ProductImage.role == "main",
                    ProductImage.id != image.id,
                )
            ):
                other.role = "gallery"
        db.flush()
        job = db.get(GenerationJob, asset.job_id)
        if job.status not in {"processing", "queued"}:
            states = set(
                db.scalars(
                    select(GeneratedAsset.status).where(GeneratedAsset.job_id == job.id)
                )
            )
            job.status = (
                "approved"
                if states <= {"approved", "published"}
                else "rejected" if states == {"rejected"} else "completed"
            )
        audit(
            db,
            tenant(value),
            actor(value),
            "image." + data.status,
            asset.product_id,
            {"status": previous},
            {"status": data.status, "role": data.role, "asset_id": asset.id},
        )
        return {"asset": serialize(asset)}


@router.post("/assets/{asset_id}/correct", status_code=202)
def correct(asset_id: str, data: CorrectionInput, value=Depends(context)):
    edit(value)
    if not data.confirm_cost:
        raise HTTPException(422, "Confirma el nuevo consumo de IA.")
    with transaction() as db:
        request_lock(db, tenant(value), data.request_key)
        asset = db.scalar(
            select(GeneratedAsset).where(
                GeneratedAsset.id == asset_id, GeneratedAsset.tenant_id == tenant(value)
            )
        )
        if not asset:
            raise HTTPException(404, "Imagen no disponible.")
        old = db.scalar(
            select(GenerationJob).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.request_key == data.request_key,
                GenerationJob.product_id == asset.product_id,
            )
        )
        if old:
            return {"job": serialize(old)}
        product_for(db, tenant(value), asset.product_id, True)
        if db.scalar(
            select(GenerationJob.id).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.product_id == asset.product_id,
                GenerationJob.status.in_(["queued", "processing"]),
            )
        ):
            raise HTTPException(409, "El producto ya tiene un trabajo activo.")
        if not available(db):
            raise HTTPException(503, "No hay worker conectado.")
        persist(db, tenant(value), actor(value), value)
        source = db.get(GenerationJob, asset.job_id)
        guard_cost(image_unit(source.model))
        payload = {
            **source.payload,
            "slots": [asset.slot],
            "quantity": 1,
            "completed_keys": [],
            "in_flight": None,
            "previous_asset_id": asset.id,
            "feedback": data.feedback,
            "previous_raw_id": asset.raw_drive_file_id,
            "history": asset.history,
            "product": serialize(product_for(db, tenant(value), asset.product_id)),
        }
        job = GenerationJob(
            tenant_id=tenant(value),
            actor=actor(value),
            product_id=asset.product_id,
            request_key=data.request_key,
            model=source.model,
            payload=payload,
            estimated_cost=image_unit(source.model),
        )
        db.add(job)
        db.flush()
        dispatch(db, job)
        audit(
            db,
            tenant(value),
            actor(value),
            "image.correction.queued",
            asset.product_id,
            after={"job_id": job.id, "asset_id": asset.id},
        )
        return {"job": serialize(job)}


class RegenerationInput(BaseModel):
    confirm_cost: bool
    request_key: str = Field(min_length=12, max_length=100)


@router.post("/assets/{asset_id}/regenerate", status_code=202)
def regenerate(asset_id: str, data: RegenerationInput, value=Depends(context)):
    edit(value)
    if not data.confirm_cost:
        raise HTTPException(422, "Confirma el nuevo consumo de IA.")
    with transaction() as db:
        asset = db.scalar(select(GeneratedAsset).where(
            GeneratedAsset.id == asset_id, GeneratedAsset.tenant_id == tenant(value)))
        if not asset:
            raise HTTPException(404, "Imagen no disponible.")
        source = db.get(GenerationJob, asset.job_id)
        cost = image_unit(source.model)
        guard_cost(cost)
        payload = {**source.payload, "slots": [asset.slot], "quantity": 1,
                   "completed_keys": [], "in_flight": None,
                   "previous_asset_id": asset.id,
                   "product": serialize(product_for(db, tenant(value), asset.product_id))}
        for field in ("previous_raw_id", "feedback", "history"):
            payload.pop(field, None)
        product_id, model = asset.product_id, source.model
    return enqueue_operation(value, "generation", data.request_key, payload,
                             product_id, model, cost)


class PublishInput(BaseModel):
    confirm: bool
    request_key: str = Field(min_length=12, max_length=100)


@router.post("/assets/{asset_id}/save", status_code=202)
def save_generated_asset(asset_id: str, data: PublishInput, value=Depends(context)):
    edit(value)
    if not data.confirm:
        raise HTTPException(422, "Confirma el guardado de la imagen aprobada.")
    with transaction() as db:
        asset = db.scalar(select(GeneratedAsset).where(
            GeneratedAsset.id == asset_id, GeneratedAsset.tenant_id == tenant(value)))
        if not asset or asset.status not in {"approved", "published"}:
            raise HTTPException(422, "Aprueba la imagen antes de guardarla.")
        product = product_for(db, tenant(value), asset.product_id)
        payload = {"asset_id": asset.id, "version": product.version}
        pid = product.id
    return enqueue_operation(value, "asset_save", data.request_key, payload, pid)


@router.post("/products/{product_id}/publish", status_code=202)
def publish(product_id: str, data: PublishInput, value=Depends(context)):
    admin(value)
    if not data.confirm:
        raise HTTPException(422, "Confirma la publicación en WooCommerce.")
    with transaction() as db:
        request_lock(db, tenant(value), data.request_key)
        product = product_for(db, tenant(value), product_id, True)
        old = db.scalar(
            select(GenerationJob).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.request_key == data.request_key,
                GenerationJob.product_id == product_id,
            )
        )
        if old:
            return {"job": serialize(old)}
        if db.scalar(
            select(GenerationJob.id).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.product_id == product_id,
                GenerationJob.status.in_(["queued", "processing"]),
            )
        ):
            raise HTTPException(409, "El producto ya tiene un trabajo activo.")
        images = db.scalars(
            select(ProductImage).where(
                ProductImage.product_id == product_id,
                ProductImage.tenant_id == tenant(value),
                ProductImage.status.in_(["approved", "published"]),
                ProductImage.role != "reference",
            )
        ).all()
        if not images:
            raise HTTPException(422, "Aprueba al menos una imagen antes de publicar.")
        if not available(db):
            raise HTTPException(503, "No hay worker conectado.")
        persist(db, tenant(value), actor(value), value)
        job = GenerationJob(
            tenant_id=tenant(value),
            product_id=product_id,
            actor=actor(value),
            kind="publication",
            request_key=data.request_key,
            provider="woocommerce",
            payload={"version": product.version, "image_ids": [i.id for i in images]},
        )
        db.add(job)
        db.flush()
        audit(
            db,
            tenant(value),
            actor(value),
            "publication.queued",
            product_id,
            after={"job_id": job.id},
        )
        return {"job": serialize(job)}


@router.get("/dashboard")
def dashboard(value=Depends(context)):
    with transaction() as db:

        def count(model, *rules):
            return db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.tenant_id == tenant(value), *rules)
            )

        stats = {
            "products": count(Product),
            "pending_products": count(Product, Product.status == "pending"),
            "low_stock": count(Product, Product.stock.between(1, 5)),
            "out_of_stock": count(Product, Product.stock == 0),
            "sync_errors": count(Product, Product.sync_status == "error"),
            "pending_jobs": count(
                GenerationJob, GenerationJob.status.in_(["queued", "processing"])
            ),
            "completed_images": count(
                GeneratedAsset,
                GeneratedAsset.status.in_(["completed", "approved", "published"]),
            ),
        }
        activity = [
            serialize(row)
            for row in db.scalars(
                select(AuditLog)
                .where(AuditLog.tenant_id == tenant(value))
                .order_by(AuditLog.created_at.desc())
                .limit(12)
            )
        ]
        from .models import OrderSnapshot
        from zoneinfo import ZoneInfo

        start = (
            datetime.now(ZoneInfo("America/Mexico_City"))
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc)
        )
        orders = db.scalars(
            select(OrderSnapshot)
            .where(OrderSnapshot.tenant_id == tenant(value))
            .order_by(OrderSnapshot.ordered_at.desc())
            .limit(10)
        ).all()
        sales = db.scalar(
            select(func.sum(OrderSnapshot.total)).where(
                OrderSnapshot.tenant_id == tenant(value),
                OrderSnapshot.currency == "MXN",
                OrderSnapshot.ordered_at >= start,
                OrderSnapshot.status.in_(["processing", "completed"]),
            )
        )
        pending = count(
            OrderSnapshot,
            OrderSnapshot.status.in_(["pending", "processing", "on-hold"]),
        )
        return {
            "stats": stats,
            "activity": activity,
            "ecommerce": (
                {
                    "sales_today": sales or 0,
                    "pending_orders": pending,
                    "orders": [serialize(o) for o in orders],
                }
                if orders
                else None
            ),
            "pos": None,
            "note": "Pedidos y ventas proceden de la última lectura o webhook de WooCommerce. POS es una integración futura.",
        }


@router.get("/events")
def events(value=Depends(context)):
    with transaction() as db:
        return {
            "items": [
                serialize(row)
                for row in db.scalars(
                    select(SyncEvent)
                    .where(SyncEvent.tenant_id == tenant(value))
                    .order_by(SyncEvent.created_at.desc())
                    .limit(100)
                )
            ]
        }


@router.get("/connections")
def connections(value=Depends(context)):
    from sync_bridge_protocol import setting

    state = lambda keys: (
        "connected" if all(setting(k) for k in keys) else "disconnected"
    )
    return {
        "items": [
            {
                "name": "Google Drive",
                "status": "connected" if value.get("creds") else "disconnected",
            },
            {
                "name": "IA · Gemini",
                "status": (
                    "connected"
                    if value.get("gemini_key") or os.getenv("AI_API_KEY")
                    else "disconnected"
                ),
            },
            {
                "name": "WooCommerce",
                "status": state(["WC_CONSUMER_KEY", "WC_CONSUMER_SECRET"]),
            },
            {"name": "WordPress", "status": state(["WP_USERNAME", "WP_APP_PASSWORD"])},
            {
                "name": "Loyverse",
                "status": "disconnected",
                "note": "Integración futura; escrituras deshabilitadas",
            },
        ],
        "note": "Estado de credenciales servidor; la última sincronización confirma la conexión remota.",
    }


@router.post("/ecommerce/refresh", status_code=202)
def ecommerce_refresh(data: PublishInput, value=Depends(context)):
    admin(value)
    if not data.confirm:
        raise HTTPException(422, "Confirma la lectura de WooCommerce.")
    return enqueue_operation(value, "ecommerce_pull", data.request_key, {})


@router.post("/import/woocommerce", status_code=202)
def import_woocommerce(data: PublishInput, value=Depends(context)):
    admin(value)
    if not data.confirm:
        raise HTTPException(422, "Confirma la importación con respaldo previo.")
    return enqueue_operation(
        value, "ecommerce_pull", data.request_key, {"import_products": True}
    )


def enqueue_operation(
    value, kind, request_key, payload, product_id=None, model="", estimated_cost=None
):
    with transaction() as db:
        request_lock(db, tenant(value), request_key)
        previous = db.scalar(
            select(GenerationJob).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.request_key == request_key,
            )
        )
        if previous:
            if previous.kind != kind or previous.product_id != product_id or previous.actor != actor(value):
                raise HTTPException(409, "request_key ya corresponde a otra operación.")
            if any(previous.payload.get(field) != payload.get(field)
                   for field in ("asset_id", "previous_asset_id", "retry_of")):
                raise HTTPException(409, "request_key ya corresponde a otro resultado.")
            return {"job": serialize(previous)}
        if kind in {"generation", "studio_generation"}:
            guard_cost(estimated_cost)
            count = len(payload["slots"]) * payload.get("quantity", 1)
            if count > int(os.getenv("MAX_IMAGES_PER_BATCH", os.getenv("MAX_BATCH_IMAGES", "300"))):
                raise HTTPException(422, "El intento supera MAX_IMAGES_PER_BATCH.")
        if product_id:
            product_for(db, tenant(value), product_id, True)
            if db.scalar(
                select(GenerationJob.id).where(
                    GenerationJob.tenant_id == tenant(value),
                    GenerationJob.product_id == product_id,
                    GenerationJob.status.in_(["queued", "processing"]),
                )
            ):
                raise HTTPException(409, "El producto ya tiene un trabajo activo.")
        if not available(db):
            raise HTTPException(
                503, "No hay worker conectado; no se aceptó la operación."
            )
        persist(db, tenant(value), actor(value), value)
        job = GenerationJob(
            tenant_id=tenant(value),
            actor=actor(value),
            kind=kind,
            request_key=request_key,
            product_id=product_id,
            model=model,
            estimated_cost=estimated_cost,
            payload=payload,
        )
        db.add(job)
        db.flush()
        dispatch(db, job)
        audit(
            db,
            tenant(value),
            actor(value),
            kind + ".queued",
            product_id,
            after={"job_id": job.id},
        )
        return {"job": serialize(job)}


@router.post("/import/sheets")
def preview_sheet(value=Depends(context)):
    admin(value)
    from studio_api import runtime
    from .imports import normalize

    _, sheet, rows = runtime.captura.snapshot(value)
    normalized, errors = normalize(rows)
    checksum = hashlib.sha256(
        json.dumps(rows, sort_keys=True, default=str).encode()
    ).hexdigest()
    key = secrets.token_urlsafe(24)
    value["platform_import"] = {
        "id": key,
        "rows": normalized,
        "errors": errors,
        "checksum": checksum,
        "sheet_id": sheet,
        "expires": time.time() + 600,
    }
    return {
        "preview_id": key,
        "rows": len(normalized),
        "errors": errors[:30],
        "sample": normalized[:8],
        "note": "Se conservan los SKU ya existentes; la hoja original no se edita.",
    }


@router.post("/import/file")
async def preview_file(source: UploadFile = File(), value=Depends(context)):
    admin(value)
    from .imports import parse_file

    try:
        raw = await source.read(2000001)
        normalized, errors = parse_file(source.filename or "", raw)
    except Exception:
        raise HTTPException(
            422,
            "Revisa el archivo: CSV UTF-8 o XLSX, máximo 2 MB, encabezados compatibles.",
        ) from None
    finally:
        await source.close()
    key = secrets.token_urlsafe(24)
    value["platform_import"] = {
        "id": key,
        "rows": normalized,
        "errors": errors,
        "checksum": hashlib.sha256(raw).hexdigest(),
        "raw": raw,
        "filename": source.filename,
        "expires": time.time() + 600,
    }
    return {
        "preview_id": key,
        "rows": len(normalized),
        "errors": errors[:30],
        "sample": normalized[:8],
        "note": "Los productos existentes se conservan. Se respaldará el archivo antes de importar.",
    }


class ImportConfirm(PublishInput):
    preview_id: str = Field(max_length=64)


@router.post("/import/commit", status_code=202)
def commit_import(data: ImportConfirm, value=Depends(context)):
    admin(value)
    preview = value.get("platform_import")
    if (
        not data.confirm
        or not preview
        or preview["id"] != data.preview_id
        or preview["expires"] < time.time()
    ):
        raise HTTPException(422, "La revisión venció. Vuelve a importar y confirma.")
    if preview["errors"] or not preview["rows"]:
        raise HTTPException(422, "Corrige los errores de la fuente antes de importar.")
    from studio_api import runtime
    from drive_service import DriveService
    from .imports import backup_catalog

    with transaction() as db:
        old = db.scalar(
            select(GenerationJob).where(
                GenerationJob.tenant_id == tenant(value),
                GenerationJob.request_key == data.request_key,
            )
        )
        if old:
            return {"job": serialize(old)}
        if not available(db):
            raise HTTPException(503, "No hay worker conectado.")
    drive = DriveService.for_session(runtime, value)
    if preview.get("sheet_id"):
        backup = drive.backup(preview["sheet_id"], "inventario_pre_import_" + uid())
    else:
        backup = drive.upload_bytes(
            preview["raw"],
            preview["filename"],
            drive.working_folder("catalog", "imports"),
            "application/octet-stream",
        )
    with transaction() as db:
        catalog_backup = backup_catalog(db, tenant(value), drive)
    result = enqueue_operation(
        value,
        "import",
        data.request_key,
        {
            "rows": preview["rows"],
            "checksum": preview["checksum"],
            "completed_keys": [],
            "source_backup_id": backup["id"],
            "catalog_backup_id": catalog_backup["id"],
        },
    )
    return result


class RetryInput(PublishInput):
    uncertainty_reviewed: bool = False


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry(job_id: str, data: RetryInput, value=Depends(context)):
    edit(value)
    with transaction() as db:
        old = db.scalar(
            select(GenerationJob).where(
                GenerationJob.tenant_id == tenant(value), GenerationJob.id == job_id
            )
        )
        if not old or old.status != "failed":
            raise HTTPException(422, "Solo se reintentan trabajos fallidos.")
        if old.kind not in {"generation", "enrichment", "stock_sync"}:
            admin(value)
        if (
            not data.confirm
            or old.payload.get("in_flight")
            and not data.uncertainty_reviewed
        ):
            raise HTTPException(
                422,
                "Verifica primero que la operación incierta no terminó y confirma el nuevo intento.",
            )
        payload = {**old.payload, "in_flight": None, "retry_of": old.id}
        kind, pid, model, cost = old.kind, old.product_id, old.model, old.estimated_cost
        if (
            kind in {"publication", "stock_sync"}
            and old.payload.get("version")
            != product_for(db, tenant(value), pid).version
        ):
            raise HTTPException(
                409,
                "La ficha cambió. Revisa el producto y confirma una nueva operación.",
            )
    return enqueue_operation(value, kind, data.request_key, payload, pid, model, cost)


@router.post("/products/{product_id}/reference-from-image/{image_id}")
def reference_from_image(product_id: str, image_id: str, value=Depends(context)):
    edit(value)
    with transaction() as db:
        product_for(db, tenant(value), product_id)
        image = db.scalar(
            select(ProductImage).where(
                ProductImage.tenant_id == tenant(value),
                ProductImage.product_id == product_id,
                ProductImage.id == image_id,
            )
        )
        if not image:
            raise HTTPException(404, "Imagen no disponible.")
        if not db.scalar(
            select(ProductImage.id).where(
                ProductImage.tenant_id == tenant(value),
                ProductImage.product_id == product_id,
                ProductImage.role == "reference",
                ProductImage.drive_file_id == image.drive_file_id,
            )
        ):
            db.add(
                ProductImage(
                    tenant_id=tenant(value),
                    product_id=product_id,
                    drive_file_id=image.drive_file_id,
                    checksum=image.checksum,
                    width=image.width,
                    height=image.height,
                    role="reference",
                    status="approved",
                    metadata_json={"reference_selected_from": image.id},
                )
            )
        audit(
            db,
            tenant(value),
            actor(value),
            "reference.selected",
            product_id,
            after={"image_id": image.id},
        )
        return {"ok": True}


@router.get("/export")
def export(format: str = "csv", value=Depends(context)):
    with transaction() as db:
        products = db.scalars(
            select(Product)
            .where(Product.tenant_id == tenant(value))
            .order_by(Product.sku)
        ).all()
        audit(
            db,
            tenant(value),
            actor(value),
            "catalog.exported",
            after={"format": format, "count": len(products)},
        )
        if format == "xlsx":
            import openpyxl

            book = openpyxl.Workbook()
            sheet = book.active
            sheet.title = "Catalogo"
            from .catalog import FIELDS

            sheet.append((*FIELDS, "parent_sku"))
            parents = {p.id: p.sku for p in products}
            for product in products:
                row = []
                for field in FIELDS:
                    cell = getattr(product, field)
                    if isinstance(cell, (list, dict)):
                        cell = json.dumps(cell, ensure_ascii=False)
                    if isinstance(cell, str) and cell[:1] in {"=", "+", "-", "@"}:
                        cell = "'" + cell
                    row.append(cell)
                sheet.append(row + [parents.get(product.parent_id, "")])
            stream = io.BytesIO()
            book.save(stream)
            return Response(
                stream.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": "attachment; filename=catalogo-rincon.xlsx"
                },
            )
        if format != "csv":
            raise HTTPException(422, "Elige CSV o Excel.")
        return Response(
            "\ufeff" + csv_export(products),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=catalogo-rincon.csv"},
        )


@router.post("/products/{product_id}/enrich", status_code=202)
def enrich_product(product_id: str, data: PublishInput, value=Depends(context)):
    edit(value)
    if not data.confirm or not value.get("gemini_key"):
        raise HTTPException(
            422, "Conecta IA y confirma el análisis antes de continuar."
        )
    from creative_pipeline import TEXT_MODEL

    with transaction() as db:
        p = product_for(db, tenant(value), product_id)
        refs = list(
            db.scalars(
                select(ProductImage.drive_file_id)
                .where(
                    ProductImage.tenant_id == tenant(value),
                    ProductImage.product_id == product_id,
                    ProductImage.role == "reference",
                    ProductImage.status == "approved",
                )
                .limit(2)
            )
        )
        if not refs:
            raise HTTPException(422, "Sube una foto de referencia del producto.")
    return enqueue_operation(
        value,
        "enrichment",
        data.request_key,
        {"references": refs, "version": p.version, "model": TEXT_MODEL},
        product_id,
    )


@router.post("/barcode")
def barcode(data: ReferenceInput, value=Depends(context)):
    from studio_api import file_path, read_barcodes

    return {"codes": read_barcodes(file_path(value, data.upload_id))}


@router.post("/products/{product_id}/sync-stock", status_code=202)
def sync_stock(product_id: str, data: PublishInput, value=Depends(context)):
    edit(value)
    if not data.confirm:
        raise HTTPException(422, "Confirma el envío del stock maestro a WooCommerce.")
    if os.getenv("STOCK_AUTHORITY", "app") != "app":
        raise HTTPException(
            409,
            "El stock lo administra la plataforma configurada como autoridad; usa la lectura de WooCommerce.",
        )
    with transaction() as db:
        p = product_for(db, tenant(value), product_id)
        if (
            p.product_type == "variable"
            or not p.woocommerce_product_id
            or p.woocommerce_stock is None
        ):
            raise HTTPException(
                422, "Publica y consulta el stock remoto antes de sincronizar."
            )
        payload = {
            "version": p.version,
            "quantity": p.stock,
            "expected_remote": p.woocommerce_stock,
        }
    return enqueue_operation(value, "stock_sync", data.request_key, payload, product_id)


@router.post("/products/{product_id}/images/{image_id}/approve-original")
def approve_original(
    product_id: str, image_id: str, data: PublishInput, value=Depends(context)
):
    edit(value)
    if not data.confirm:
        raise HTTPException(422, "Confirma el uso de la foto original en la galería.")
    with transaction() as db:
        product_for(db, tenant(value), product_id, True)
        original = db.scalar(
            select(ProductImage).where(
                ProductImage.tenant_id == tenant(value),
                ProductImage.product_id == product_id,
                ProductImage.id == image_id,
                ProductImage.role == "reference",
            )
        )
        if not original:
            raise HTTPException(404, "Referencia original no disponible.")
        existing = db.scalar(
            select(ProductImage).where(
                ProductImage.tenant_id == tenant(value),
                ProductImage.product_id == product_id,
                ProductImage.drive_file_id == original.drive_file_id,
                ProductImage.role != "reference",
            )
        )
        if not existing:
            copy = ProductImage(
                tenant_id=tenant(value),
                product_id=product_id,
                drive_file_id=original.drive_file_id,
                role="gallery",
                status="approved",
                width=original.width,
                height=original.height,
                checksum=original.checksum,
                mime_type=original.mime_type,
                metadata_json={"original_approved_from": original.id},
            )
            db.add(copy)
        audit(
            db,
            tenant(value),
            actor(value),
            "original.approved",
            product_id,
            after={"reference_id": original.id},
        )
        return {"ok": True}
