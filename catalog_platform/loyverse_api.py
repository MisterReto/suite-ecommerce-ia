"""Authenticated Loyverse connections, read-only comparison and confirmed queued creation."""
from copy import deepcopy
import secrets
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select
from .api import context, admin
from .database import transaction
from .models import GenerationJob
from .security import seal, unseal, cipher
from . import loyverse_connections as connections
from .loyverse_export import Exporter, fingerprint, google_clients, preview_bytes, bounded_entries
from .loyverse_jobs import KIND, enqueue, public_job, owned, control

router = APIRouter(prefix="/api/loyverse", tags=["Loyverse"])


class TestConnection(BaseModel):
    token: SecretStr | None = None
    connection_id: str | None = Field(default=None, max_length=36)


class SaveConnection(BaseModel):
    test_token: str = Field(min_length=32, max_length=100)
    name: str = Field(min_length=1, max_length=80)
    store_id: str = Field(min_length=1, max_length=100)
    connection_id: str | None = Field(default=None, max_length=36)


@router.get("/connections")
def list_connections(value=Depends(context)):
    cipher()
    with transaction() as db:
        rows = connections.connections(db, value["platform_tenant"], value["email"])
        return {"connections": [connections.public_connection(row) for row in rows.values()],
                "inventory_sync_enabled": False}


@router.post("/connections/test")
def test_connection(data: TestConnection, value=Depends(context)):
    admin(value)
    token = data.token.get_secret_value().strip() if data.token else ""
    if not token and data.connection_id:
        with transaction() as db:
            row = connections.connections(db, value["platform_tenant"], value["email"]).get(data.connection_id)
            if not row:
                raise HTTPException(404, "Conexión no disponible.")
            token = row["token"]
    if not token or len(token) > 4096 or any(c.isspace() for c in token):
        raise HTTPException(422, "Introduce un token Loyverse válido.")
    engine = Exporter(token)
    try:
        identity = engine.identity()
        challenge = secrets.token_urlsafe(32)
        # Pending credentials are encrypted too; web-session persistence never stores raw tokens.
        tests = value.setdefault("loyverse_connection_tests", {})
        for key in list(tests):
            if tests[key]["expires"] < time.time() or len(tests) >= 5:
                del tests[key]
        tests[challenge] = {"credentials": seal({**identity, "token": token}),
            "expires": time.time() + 600, "tenant": value["platform_tenant"],
            "actor": value["email"], "connection_id": data.connection_id}
        return {"ok": True, "test_token": challenge, "merchant_name": identity["merchant_name"], "stores": identity["stores"]}
    except Exception as exc:
        if data.connection_id:
            with transaction() as db:
                rows = connections.connections(db, value["platform_tenant"], value["email"], lock=True)
                if data.connection_id in rows:
                    rows[data.connection_id].update(status="error", checked_at=time.time())
                    from .accounts import put
                    put(db, value["platform_tenant"], value["email"], connections.PROVIDER, rows)
        raise HTTPException(502, str(exc).replace(token, "[redacted]")[:500]) from None
    finally:
        engine.close()


@router.post("/connections")
def save_connection(data: SaveConnection, value=Depends(context)):
    admin(value)
    test = value.get("loyverse_connection_tests", {}).get(data.test_token)
    if (not test or test["expires"] < time.time() or test["tenant"] != value["platform_tenant"]
            or test["actor"] != value["email"] or test["connection_id"] != data.connection_id or not data.name.strip()):
        raise HTTPException(422, "Prueba la conexión vigente antes de guardarla.")
    with transaction() as db:
        return {"connection": connections.save(db, value, unseal(test["credentials"]), data.name, data.store_id, data.connection_id)}


@router.delete("/connections/{connection_id}")
def delete_connection(connection_id: str, value=Depends(context)):
    admin(value)
    with transaction() as db:
        connections.remove(db, value, connection_id)
    value.pop("loyverse_catalog_cache", None)
    value.pop("loyverse_preview", None)
    value.pop("loyverse_connection_tests", None)
    return {"ok": True}


def connection_for(value, connection_id, store_id):
    with transaction() as db:
        return connections.selected(db, value, connection_id, store_id)


@router.get("/catalog")
def catalog(connection_id: str, store_id: str, q: str = Query("", max_length=160),
            category: str = Query("", max_length=240), brand: str = Query("", max_length=240),
            kind: str = Query("", max_length=20), comparison: str = Query("", max_length=20),
            remote: bool = False, refresh: bool = False, offset: int = Query(0, ge=0),
            limit: int = Query(50, ge=1, le=100), value=Depends(context)):
    connection = connection_for(value, connection_id, store_id)
    cache_key = fingerprint([value["platform_tenant"], connection_id, connection["revision"], store_id])
    cached = value.get("loyverse_catalog_cache")
    engine = None
    try:
        if refresh or not cached or cached["key"] != cache_key or cached["expires"] < time.time():
            engine = Exporter(connection["token"]).load(value).remote()
            cached = {"key": cache_key, "rows": engine.catalog(), "remote": engine.remote_rows(store_id),
                      "expires": time.time() + 60, "checked_at": time.time()}
            value["loyverse_catalog_cache"] = cached
        all_rows = cached["remote"] if remote else cached["rows"]
        rows = [row for row in all_rows if (not q or q.casefold() in (row["sku"] + " " + row["name"]).casefold())
                and (not category or row.get("category") == category) and (not brand or row.get("brand") == brand)
                and (not kind or row.get("kind") == kind) and (not comparison or row.get("comparison") == comparison)]
        return {"rows": rows[offset:offset + limit], "total": len(rows), "checked_at": cached["checked_at"],
                "categories": sorted({row["category"] for row in all_rows if row.get("category")}),
                "brands": sorted({row["brand"] for row in all_rows if row.get("brand")}),
                "summary": {state: sum(r["comparison"] == state for r in cached["rows"])
                            for state in ("existing", "missing", "partial")}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, str(exc).replace(connection["token"], "[redacted]")[:500]) from None
    finally:
        if engine: engine.close()


class Selection(BaseModel):
    kind: Literal["simple", "family", "variant"]
    sku: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class Options(BaseModel):
    images: bool = True
    create_categories: bool = False


class Preview(BaseModel):
    connection_id: str = Field(min_length=1, max_length=36)
    store_id: str = Field(min_length=1, max_length=100)
    selections: list[Selection] = Field(min_length=1, max_length=300)
    options: Options = Field(default_factory=Options)


@router.post("/preview")
def preview(data: Preview, value=Depends(context)):
    connection = connection_for(value, data.connection_id, data.store_id)
    engine = None
    try:
        options = data.options.model_dump()
        engine = Exporter(connection["token"]).load(value, images=options["images"]).remote()
        chosen = {s.kind + ":" + s.sku: s.model_dump() for s in data.selections}
        families = {s.sku for s in data.selections if s.kind == "family"}
        entries, previews, errors, omitted = [], [], [], []
        for selection in chosen.values():
            try:
                parent, _, _ = engine.resolve(selection)
                if selection["kind"] == "variant" and parent["sku"] in families:
                    omitted.append(selection)
                    continue
                review = engine.review(selection, options)
                entries.extend(bounded_entries(selection, engine.snapshot(selection)))
                previews.append(review)
            except (ValueError, KeyError) as exc:
                errors.append({"selection": selection, "message": str(exc)[:500]})
        if sum(len(p["items"]) for p in previews) > 1000:
            raise ValueError("El lote supera mil variantes. Divide la selección.")
        token = secrets.token_urlsafe(32)
        store_name = next(s["name"] for s in connection["stores"] if s["id"] == data.store_id)
        value["loyverse_preview"] = {"token": token, "entries": entries, "errors": errors,
            "connection_id": connection["id"], "revision": connection["revision"],
            "store_id": data.store_id, "store_name": store_name, "options": options,
            "tenant": value["platform_tenant"], "actor": value["email"], "expires": time.time() + 600}
        for p in previews:
            for row in p["items"]:
                if row["image_name"]:
                    from urllib.parse import urlencode
                    row["image_url"] = "/api/loyverse/preview-image?" + urlencode({"preview_token": token, "name": row["image_name"]})
        return {"preview_token": token, "previews": previews, "errors": errors, "omitted": omitted,
                "connection_name": connection["name"], "merchant_name": connection["merchant_name"], "store_name": store_name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, str(exc).replace(connection["token"], "[redacted]")[:500]) from None
    finally:
        if engine: engine.close()


def current_preview(value, token):
    preview = value.get("loyverse_preview")
    if (not preview or preview["token"] != token or preview["expires"] < time.time()
            or preview["tenant"] != value["platform_tenant"] or preview["actor"] != value["email"]):
        raise HTTPException(422, "Revisa una vista previa vigente antes de publicar.")
    return preview


@router.get("/preview-image")
def preview_image(preview_token: str, name: str, value=Depends(context)):
    preview = current_preview(value, preview_token)
    files = [f for entry in preview["entries"] for f in entry["source"]["IMAGE_FILES"] if f["name"] == name]
    if not files:
        raise HTTPException(404, "Imagen no disponible en esta revisión.")
    _, drive = google_clients(value)
    try:
        return Response(preview_bytes(drive, files[0]), media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
    except Exception:
        raise HTTPException(502, "No se pudo abrir la imagen seleccionada.") from None


class Confirm(BaseModel):
    preview_token: str = Field(min_length=32, max_length=100)
    request_key: str = Field(min_length=12, max_length=64)
    confirmation: str = Field(default="", max_length=20)


@router.post("/jobs", status_code=202)
def submit(data: Confirm, value=Depends(context)):
    admin(value)
    cached = current_preview(value, data.preview_token)
    if data.confirmation != "PUBLICAR" or cached["errors"] or not cached["entries"]:
        raise HTTPException(422, "Revisa un lote sin errores y escribe PUBLICAR para crear artículos reales.")
    return enqueue(value, cached, data.request_key)


@router.get("/jobs")
def jobs(value=Depends(context)):
    with transaction() as db:
        rows = db.scalars(select(GenerationJob).where(GenerationJob.tenant_id == value["platform_tenant"],
            GenerationJob.actor == value["email"], GenerationJob.kind == KIND)
            .order_by(GenerationJob.created_at.desc()).limit(200)).all()
        if any(r.status == "queued" for r in rows):
            from .worker_wakeup import notify
            notify()
        return {"jobs": [public_job(r) for r in rows]}


class Control(BaseModel):
    action: Literal["pause", "resume", "cancel", "retry"]
    confirmation: str = Field(default="", max_length=20)


@router.post("/jobs/{job_id}/control")
def job_control(job_id: str, data: Control, value=Depends(context)):
    return {"job": control(value, job_id, data.action, data.confirmation == "PUBLICAR")}


@router.get("/jobs/{job_id}/log")
def job_log(job_id: str, value=Depends(context)):
    import json
    with transaction() as db:
        job = owned(db, value, job_id)
        raw = json.dumps(public_job(job), ensure_ascii=False, indent=2).encode()
    return Response(raw, media_type="application/json", headers={
        "Content-Disposition": 'attachment; filename="loyverse_resultado.json"', "Cache-Control": "private, no-store"})
