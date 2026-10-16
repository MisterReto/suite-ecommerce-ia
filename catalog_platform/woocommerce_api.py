"""React-facing review/queue boundary for the preserved Colab WooCommerce uploader."""
import time
import hashlib
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from .api import context, admin
from .database import transaction
from .models import GenerationJob, GenerationBatch, Product
from .woocommerce_compare import read_store, compare, quantity
from .woocommerce_export import Exporter, fingerprint, connection_status, safe_error, store_url
from .woocommerce_jobs import KIND, enqueue, public_job

router = APIRouter(prefix="/api/woocommerce")


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["simple", "family", "variant"]
    sku: str = Field(min_length=1, max_length=160)


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")
    images: bool = True
    stock: bool = False
    tags: bool = False
    allow_published_family: bool = False
    status: Literal["publish", "draft"] = "publish"


class Preview(BaseModel):
    selection: Selection
    options: Options = Field(default_factory=Options)


class Confirm(BaseModel):
    preview_token: str = Field(min_length=64, max_length=64)
    request_key: str = Field(min_length=16, max_length=80)
    confirm: bool = False


class BatchPreview(BaseModel):
    selections: list[Selection] = Field(min_length=1, max_length=100)
    options: Options = Field(default_factory=Options)


@router.get("/connection")
def connection(value=Depends(context)):
    return connection_status()


@router.get("/inventory-comparison")
def inventory_comparison(refresh: bool = False, value=Depends(context)):
    engine = None
    try:
        if not connection_status()["configured"]:
            raise HTTPException(503, "Configura la conexión de WooCommerce para comparar el inventario.")
        origin, tenant = store_url(), value["platform_tenant"]
        cached = value.get("woocommerce_inventory_cache")
        if (not refresh and cached and cached["expires"] > time.time()
                and cached["store"] == origin and cached["tenant"] == tenant):
            snapshot = cached["snapshot"]
        else:
            engine = Exporter()
            snapshot = read_store(engine)
            value["woocommerce_inventory_cache"] = {"snapshot": snapshot, "store": origin,
                "tenant": tenant, "expires": time.time() + 45}
        with transaction() as db:
            products = db.scalars(select(Product).where(Product.tenant_id == tenant,
                Product.status.notin_(["deleted", "archived"]))).all()
            by_id = {row.id: row for row in products}
            local = [{"sku": row.sku, "name": row.name, "stock": quantity(row.stock),
                "kind": "family" if row.product_type == "variable" else
                    "variant" if row.product_type in {"variation", "variant"} or row.parent_id else "simple",
                "parent_sku": by_id[row.parent_id].sku if row.parent_id in by_id else "",
                "brand": row.brand, "category": row.category} for row in products]
        return {**compare(local, snapshot["rows"]), "store": origin,
            "checked_at": snapshot["checked_at"], "woocommerce_products": snapshot["products"],
            "woocommerce_variations": snapshot["variations"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, safe_error(exc)) from None
    finally:
        if engine:
            engine.close()


@router.post("/connection/test")
def test_connection(value=Depends(context)):
    admin(value)
    engine = None
    try:
        engine = Exporter()
        engine.ns["wc"]("GET", "products", params={"per_page": 1})
        media_ok = False
        if connection_status()["images_configured"]:
            response = engine.ns["wordpress_session"]().get(engine.ns["WP_API"] + "/media",
                params={"per_page": 1}, timeout=60)
            engine.ns["comprobar_respuesta"](response, "Consultar medios WordPress")
            media_ok = True
        return {"ok": True, "wordpress_ok": media_ok, "store": store_url(),
                "message": "WooCommerce y WordPress responden correctamente." if media_ok
                else "WooCommerce responde correctamente. Configura WordPress para incluir imágenes."}
    except Exception as exc:
        raise HTTPException(502, safe_error(exc)) from None
    finally:
        if engine:
            engine.close()


@router.get("/catalog")
def catalog(q: str = Query("", max_length=160), category: str = Query("", max_length=240),
            brand: str = Query("", max_length=240), kind: str = "", offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=250), value=Depends(context)):
    engine = None
    try:
        cached = value.get("woocommerce_catalog_cache")
        if cached and cached["expires"] > time.time() and cached["store"] == store_url():
            all_rows = cached["rows"]
        else:
            engine = Exporter().load(value, include_images=False)
            all_rows = engine.catalog()
            value["woocommerce_catalog_cache"] = {"rows": all_rows, "store": store_url(), "expires": time.time() + 45}
        rows = [row for row in all_rows if (not q or q.casefold() in (row["sku"] + " " + row["name"]).casefold())
                and (not category or row["category"] == category) and (not brand or row["brand"] == brand)
                and (not kind or row["kind"] == kind)]
        return {"rows": rows[offset:offset + limit], "total": len(rows),
                "categories": sorted({row["category"] for row in all_rows if row["category"]}),
                "brands": sorted({row["brand"] for row in all_rows if row["brand"]})}
    except Exception as exc:
        raise HTTPException(422, safe_error(exc)) from None
    finally:
        if engine:
            engine.close()


@router.post("/preview")
def preview(data: Preview, value=Depends(context)):
    engine = None
    try:
        options, selection = data.options.model_dump(), data.selection.model_dump()
        engine = Exporter().load(value, include_images=options["images"])
        public = engine.preview(selection["kind"], selection["sku"], options)
        public["warnings"] = engine.preflight(selection["kind"], selection["sku"], options, review_only=True)
        source = engine.snapshot(selection["kind"], selection["sku"])
        token = fingerprint(source, {**selection, "store": store_url()}, options)
        previews = value.setdefault("woocommerce_previews", {})
        for old in list(previews):
            if previews[old]["expires"] < time.time() or len(previews) >= 8:
                del previews[old]
        previews[token] = {"token": token, "selection": selection, "options": options,
                           "source": source, "store_url": store_url(), "expires": time.time() + 600,
                           "blockers": public["warnings"]}
        return {"preview": public, "preview_token": token, "options": options, "store": store_url()}
    except Exception as exc:
        raise HTTPException(422, safe_error(exc)) from None
    finally:
        if engine:
            engine.close()


@router.post("/jobs", status_code=202)
def submit(data: Confirm, value=Depends(context)):
    admin(value)
    cached = value.get("woocommerce_previews", {}).get(data.preview_token)
    if not data.confirm or not cached or cached["expires"] < time.time():
        raise HTTPException(422, "Revisa la vista previa vigente y confirma la carga.")
    if cached["store_url"] != store_url():
        raise HTTPException(409, "La tienda cambió. Prepara una nueva vista previa.")
    if cached.get("blockers"):
        raise HTTPException(422, cached["blockers"][0])
    return {"job": enqueue(value, cached, data.request_key)}


@router.get("/jobs")
def jobs(value=Depends(context)):
    with transaction() as db:
        rows = db.scalars(select(GenerationJob).where(GenerationJob.tenant_id == value["platform_tenant"],
            GenerationJob.actor == value["email"], GenerationJob.kind == KIND)
            .order_by(GenerationJob.created_at.desc()).limit(100)).all()
        if any(job.status == "queued" for job in rows):
            from .worker_wakeup import notify
            notify()
        return {"jobs": [public_job(job) for job in rows]}


@router.post("/batch-preview")
def batch_preview(data: BatchPreview, value=Depends(context)):
    engine = None
    try:
        options = data.options.model_dump()
        engine = Exporter().load(value, include_images=options["images"])
        requested = [item.model_dump() for item in data.selections]
        families = {item["sku"] for item in requested if item["kind"] == "family"}
        seen, selected, omitted = set(), [], []
        for item in requested:
            identity = (item["kind"], item["sku"])
            parent = engine.ns["sku_padre"](engine.ns["VARIANTES"].get(item["sku"], {}))
            if identity in seen or item["kind"] == "variant" and parent in families:
                omitted.append(item)
                continue
            seen.add(identity)
            selected.append(item)
        previews, errors, private = [], [], []
        for selection in selected:
            try:
                public = engine.preview(selection["kind"], selection["sku"], options)
                public["warnings"] = engine.preflight(selection["kind"], selection["sku"], options, review_only=True)
                source = engine.snapshot(selection["kind"], selection["sku"])
                token = fingerprint(source, {**selection, "store": store_url()}, options)
                previews.append(public)
                private.append({"token": token, "selection": selection, "options": options,
                    "source": source, "store_url": store_url(), "expires": time.time() + 600,
                    "blockers": public["warnings"]})
            except (ValueError, KeyError) as exc:
                errors.append({"selection": selection, "message": safe_error(exc)})
        if sum(len(item["items"]) for item in previews) > int(os.getenv("WOOCOMMERCE_MAX_BATCH_PRODUCTS", "1000")):
            raise ValueError("El lote supera el límite de productos. Divide la selección.")
        token = fingerprint([item["source"] for item in private], selected, {**options, "store": store_url()})
        for item in private:
            item["bulk_token"] = token
        value["woocommerce_batch_preview"] = {"token": token, "previews": private,
            "errors": errors, "expires": time.time() + 600, "store_url": store_url()}
        return {"previews": previews, "errors": errors, "omitted": omitted,
                "preview_token": token, "options": options, "store": store_url()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, safe_error(exc)) from None
    finally:
        if engine:
            engine.close()


@router.post("/batch-jobs", status_code=202)
def submit_batch(data: Confirm, value=Depends(context)):
    admin(value)
    cached = value.get("woocommerce_batch_preview")
    if (not data.confirm or not cached or cached["token"] != data.preview_token
            or cached["expires"] < time.time() or cached["errors"] or not cached["previews"]):
        raise HTTPException(422, "Revisa un lote vigente sin errores y confirma la carga.")
    if cached["store_url"] != store_url():
        raise HTTPException(409, "La tienda cambió. Revisa el lote otra vez.")
    if any(item.get("blockers") for item in cached["previews"]):
        raise HTTPException(422, "Autoriza añadir variantes a las familias publicadas y revisa el lote otra vez.")
    with transaction() as db:
        key = "wc:" + data.request_key
        from .queue import request_lock
        request_lock(db, value["platform_tenant"], key)
        existing = db.scalar(select(GenerationBatch).where(
            GenerationBatch.tenant_id == value["platform_tenant"], GenerationBatch.request_key == key))
        if existing:
            jobs = db.scalars(select(GenerationJob).where(GenerationJob.batch_id == existing.id)).all()
            if existing.actor != value["email"] or any(job.payload.get("bulk_token") != cached["token"] for job in jobs):
                raise HTTPException(409, "La clave de solicitud ya corresponde a otro lote.")
            return {"batch_id": existing.id, "jobs": [public_job(job) for job in jobs]}
        batch = GenerationBatch(tenant_id=value["platform_tenant"], actor=value["email"], request_key=key,
            product_count=len(cached["previews"]), image_count=0, estimated_cost=0)
        db.add(batch)
        db.flush()
        jobs = []
        for preview in cached["previews"]:
            suffix = hashlib.sha256((preview["selection"]["kind"] + ":" + preview["selection"]["sku"]).encode()).hexdigest()[:16]
            jobs.append(enqueue(value, preview, "wc:" + data.request_key + ":" + suffix, batch.id, db))
        return {"batch_id": batch.id, "jobs": jobs}


@router.get("/jobs/{job_id}")
def job(job_id: str, value=Depends(context)):
    with transaction() as db:
        row = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id,
            GenerationJob.tenant_id == value["platform_tenant"], GenerationJob.actor == value["email"],
            GenerationJob.kind == KIND))
        if not row:
            raise HTTPException(404, "Carga no disponible.")
        if row.status == "queued":
            from .worker_wakeup import notify
            notify()
        return {"job": public_job(row)}
