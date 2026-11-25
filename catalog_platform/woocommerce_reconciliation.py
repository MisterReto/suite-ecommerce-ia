"""Preview and apply managed catalog changes on the existing queue."""
from collections import Counter
from contextlib import closing
import json
import os
import tempfile
import time
from pathlib import Path

from sqlalchemy import func, or_, select, text, update

from . import queue
from .catalog import audit
from .database import transaction
from .models import AuditLog, GenerationJob, IntegrationMapping, Product
from .reconciliation_index import CatalogIndex, family_digest, norm
from .reconciliation_store import pages, snapshot, LIMIT, PAGE
from .redis_broker import connection
from .security import require_role
from .woocommerce_export import Exporter, store_url

KIND = "wc_reconcile"
ELIGIBLE = {"missing","publish","remove"}
TTL = 3600


def stream(db, query):
    return db.execute(query.execution_options(yield_per=128))


def local_snapshot(index, tenant, origin):
    dbi = index.db
    with transaction() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        for p in stream(db,select(Product.id,Product.sku,Product.barcode,Product.product_type,
            Product.parent_id,Product.status,Product.version,Product.woocommerce_product_id,
            Product.woocommerce_variation_id,Product.created_at).where(Product.tenant_id==tenant)):
            kind = "variation" if p.parent_id or p.product_type in {"variant","variation"} else p.product_type
            dbi.execute("INSERT INTO local VALUES(?,?,?,?,?,?,?,?)",(p.id,norm(p.sku),norm(p.barcode),
                kind,p.parent_id,p.status,p.version,p.sku))
            rid = p.woocommerce_variation_id if kind=="variation" else p.woocommerce_product_id
            if rid:
                dbi.execute("INSERT INTO mapping VALUES(?,?,?)",(p.id,rid,p.woocommerce_product_id if kind=="variation" else 0))
        for pid,sku in stream(db,select(AuditLog.product_id,AuditLog.before["sku"].as_string()).where(AuditLog.tenant_id==tenant,AuditLog.action=="product.deleted")):
            dbi.execute("UPDATE local SET sku=?,display=? WHERE id=? AND status='deleted'",(norm(sku),sku,pid))
        for pid,rid,parent in stream(db,select(IntegrationMapping.internal_product_id,
            IntegrationMapping.external_id,IntegrationMapping.parent_external_id).where(
                IntegrationMapping.tenant_id==tenant,IntegrationMapping.provider=="woocommerce")):
            dbi.execute("INSERT INTO mapping VALUES(?,?,?)",(pid,rid,parent or 0))
    if not dbi.execute("SELECT 1 FROM local WHERE status NOT IN (\x27deleted\x27,\x27archived\x27) LIMIT 1").fetchone():
        raise ValueError("El inventario validado está vacío. Comprueba la carpeta y la sincronización de Sheets.")


def page_key(run, page):
    return f"rincon:wc-reconcile:{run}:{page}"


def read_page(run,page):
    raw = connection().get(page_key(run,page))
    if raw is None:
        raise ValueError("La vista previa expiró. Genera una nueva.")
    return json.loads(raw)


def result_view(row):
    return {k:row[k] for k in ("key","sku","category","remote_status","remote","kind")}


def process(job, owner):
    job["_owner"] = owner
    payload = job["payload"]
    origin = store_url()
    if payload["store"] != origin:
        raise ValueError("Cambió la tienda. Genera otra vista previa.")
    require_role({"email":job["actor"]},"admin")
    if payload.get("direction") != "app_to_store":
        raise ValueError("Genera una nueva vista previa para sincronizar WooCommerce.")
    root = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root or root != job["tenant_id"]:
        raise ValueError("Selecciona la carpeta del inventario principal antes de sincronizar la tienda.")
    last = 0
    def checkpoint(force=False):
        nonlocal last
        if force or time.monotonic()-last >= 5:
            queue.checkpoint(job["id"],owner)
            last = time.monotonic()
    applying = bool(payload.get("preview"))
    counts = Counter()
    with tempfile.TemporaryDirectory() as work, closing(Exporter(write=applying)) as engine:
        index = CatalogIndex(Path(work)/"catalog.db")
        with closing(index.db):
            local_snapshot(index,job["tenant_id"],origin)
            snapshot(engine,index,checkpoint)
            queue.checkpoint(job["id"],owner,message="Comparando el inventario validado",progress=40)
            if applying:
                apply_selection(index,engine,job,checkpoint,counts)
            else:
                page, batch = 0,[]
                for number,row in enumerate(index.rows(),1):
                    if number>LIMIT:
                        raise ValueError("El catálogo combinado supera el límite de 20 000 registros.")
                    checkpoint()
                    counts[row["category"]] += 1
                    batch.append(row)
                    if len(batch)==PAGE:
                        connection().setex(page_key(job["id"],page),TTL,json.dumps(batch))
                        page,batch = page+1,[]
                if batch:
                    connection().setex(page_key(job["id"],page),TTL,json.dumps(batch))
                    page += 1
                queue.checkpoint(job["id"],owner,updates={"pages":page,"counts":dict(counts)},progress=99)
    return True


def apply_selection(index, engine, job, checkpoint, counts):
    payload = job["payload"]
    dbi = index.db
    dbi.execute("CREATE TABLE approved(key TEXT PRIMARY KEY, data TEXT)")
    selected = set(payload["keys"])
    for page in range(payload["pages"]):
        checkpoint()
        for row in read_page(payload["preview"],page):
            if row["category"] in ELIGIBLE and (payload["all"] or row["key"] in selected):
                dbi.execute("INSERT INTO approved VALUES(?,?)",(row["key"],json.dumps(row)))
                selected.discard(row["key"])
    if selected:
        raise ValueError("La selección no pertenece a esta vista previa.")
    # Complete both inventories and verify every preview page before the first change.
    dbi.execute("CREATE TABLE created(id INTEGER PRIMARY KEY)")
    dbi.execute("CREATE TABLE current(key TEXT PRIMARY KEY)")
    for row in index.rows():
        checkpoint()
        if row["category"] in ELIGIBLE:
            dbi.execute("INSERT INTO current VALUES(?)",(row["key"],))
    total = dbi.execute("SELECT count(*) FROM approved").fetchone()[0]
    batch = []
    loaded = False
    for key,data,current in dbi.execute("SELECT a.key,a.data,c.key FROM approved a LEFT JOIN current c ON c.key=a.key ORDER BY CASE WHEN json_extract(a.data,'$.kind')='variable' THEN 0 ELSE 1 END"):
        checkpoint()
        row = json.loads(data)
        outcome = "changed" if current else "stale"
        if current:
            checkpoint(True)
            if row["category"]=="missing":
                if not loaded:
                    from .accounts import load
                    with transaction() as db:
                        value = load(db,job["tenant_id"],job["actor"])
                    value.update(email=job["actor"],platform_tenant=job["tenant_id"])
                    engine.load(value,include_images=True)
                    loaded = True
                outcome = create_remote(engine,row,job,dbi)
            else:
                outcome = set_remote_status(engine,row,job)
        batch.append((row,outcome))
        if len(batch)>=PAGE or current:
            save_results(batch,job,counts)
            batch.clear()
            if total and not current:
                queue.checkpoint(job["id"],job["_owner"],progress=40+int(59*sum(counts.values())/total),
                                 updates={"counts":dict(counts)})
    save_results(batch,job,counts)
    queue.checkpoint(job["id"],job["_owner"],updates={"counts":dict(counts)},progress=99)


def create_remote(engine,row,job,dbi):
    sku = row["sku"]
    kind = {"variable":"family","variation":"variant","simple":"simple"}.get(row["kind"])
    if not kind:
        return "stale"
    with transaction() as db:
        version = db.scalar(select(Product.version).where(Product.id==row["local"],
            Product.tenant_id==job["tenant_id"],Product.status.notin_(["deleted","archived"])))
    if version!=row["version"]:
        return "stale"
    source = {"family":"PADRES","variant":"VARIANTES","simple":"SIMPLES"}[kind]
    if sku not in engine.ns[source]:
        row["detail"]="SKU ausente de la hoja de publicación."
        return "failed"
    if kind=="family":
        members = sorted(norm(v["sku"]) for v in engine.ns["hijos_familia"](sku))
        local = dbi.execute("SELECT sku,version FROM local WHERE parent=? AND status NOT IN ('archived','deleted') ORDER BY sku",(row["local"],)).fetchall()
        if not members or members!=[v[0] for v in local] or family_digest(local)!=row["children_hash"]:
            return "stale"
        approved = dbi.execute("""SELECT count(*) FROM approved a JOIN current c ON c.key=a.key
            WHERE json_extract(a.data,'$.parent_sku')=? AND json_extract(a.data,'$.category')='missing'""",(sku,)).fetchone()[0]
        if approved!=len(members):
            row["detail"]="Selecciona la familia y todas sus variantes para crearla."
            return "skipped"
    if kind=="variant":
        if engine.ns["sku_padre"](engine.ns[source][sku])!=row["parent_sku"]:
            return "stale"
        parent=engine.ns["buscar_producto"](row["parent_sku"])
        if not parent or parent.get("type")!="variable" or parent.get("status")!="publish":
            row["detail"]="El padre debe estar publicado."
            return "skipped"
        def lookup():
            return engine.ns["buscar_variacion"](parent["id"],sku)
    else:
        def lookup():
            return engine.ns["buscar_producto"](sku)
    existing = lookup()
    if existing:
        row["remote"]=existing["id"]
        return "created" if existing.get("status")=="publish" and dbi.execute("SELECT 1 FROM created WHERE id=?",(existing["id"],)).fetchone() else "skipped"
    def guard(operation,modifying):
        if modifying:
            require_role({"email":job["actor"]},"admin")
            queue.checkpoint(job["id"],job["_owner"],updates={"in_flight":{"sku":sku}})
    session=engine.ns["wc_session"]
    session.before=guard
    try:
        options={"images":bool(engine.ns["fotos_sku"](sku)), "status":"publish","tags":True,
                 "stock":True,"allow_published_family":True}
        engine.execute(kind,sku,options)
        result=lookup()
        if result and norm(result.get("sku"))==norm(sku) and result.get("status")=="publish":
            row["remote"]=result["id"]
            if kind=="family":
                for member in engine.ns["hijos_familia"](sku):
                    child=engine.ns["buscar_variacion"](result["id"],member["sku"])
                    if not child or child.get("status")!="publish":
                        return "uncertain"
                    dbi.execute("INSERT OR IGNORE INTO created VALUES(?)",(child["id"],))
            return "created"
        return "uncertain"
    except queue.JobCancelled:
        raise
    except Exception as exc:
        from .woocommerce_export import safe_error
        row["detail"]=safe_error(exc)[:240]
        if any(code in str(exc) for code in ("HTTP 401","HTTP 403")):
            raise
        return "failed"
    finally:
        session.before=None


def set_remote_status(engine,row,job):
    rid,parent = row["remote"],row["parent"]
    endpoint = f"products/{parent}/variations/{rid}" if parent else f"products/{rid}"
    # Check the live product immediately before the reversible write.
    session, url = engine.ns["wc_session"],engine.ns["WC_API"]+"/"+endpoint
    with transaction() as db:
        local = db.execute(select(Product.status,Product.version).where(
            Product.tenant_id==job["tenant_id"],Product.id==row["local"])).first()
        tokens = {row["remote_sku"],row["barcode"]} - {""}
        reused = db.scalar(select(Product.id).where(Product.tenant_id==job["tenant_id"],
            Product.status!="deleted",or_(func.lower(func.trim(Product.sku)).in_(tokens),
                func.lower(func.trim(Product.barcode)).in_(tokens))).limit(1))
        if row["category"]=="publish":
            if not local or local.status in ("archived","deleted") or local.version!=row["version"]:
                return "stale"
        elif (row["local"] and (not local or tuple(local)!=("deleted",row["version"]))) or reused:
            return "stale"
    # A failed verification read aborts the run. Writes are never blindly retried.
    try:
        response = session.get(url,params={"context":"edit","_fields":"id,parent_id,type,sku,global_unique_id,status,variations"},timeout=(8,30))
    except ValueError as exc:
        if "HTTP 404" in str(exc):
            return "stale"
        raise
    current = engine.ns["comprobar_respuesta"](response,endpoint)
    if (current.get("id")!=rid or norm(current.get("sku"))!=row["remote_sku"]
        or norm(current.get("global_unique_id"))!=row["barcode"] or current.get("parent_id",parent)!=parent
        or (not parent and current.get("type")!=row["kind"])
        or current.get("status")!=row["remote_status"]):
        return "stale"
    if row["kind"]=="variable" and row["category"]=="remove":
        expected = current.get("variations")
        if not isinstance(expected,list) or len(set(expected))!=len(expected):
            raise ValueError("La tienda devolvió una familia incompleta.")
        remaining = set(expected)
        def children():
            for child in pages(engine,endpoint+"/variations",lambda:queue.checkpoint(job["id"],job["_owner"])):
                if child.get("parent_id",rid)!=rid:
                    raise ValueError("La familia cambió. Actualiza la vista previa.")
                remaining.discard(child["id"])
                yield child["id"],norm(child["sku"]),norm(child.get("global_unique_id")),child["status"]
        if family_digest(children())!=row["family"] or remaining:
            return "stale"
    require_role({"email":job["actor"]},"admin")
    queue.checkpoint(job["id"],job["_owner"],updates={"in_flight":{"sku":row["sku"],"remote":rid}})
    try:
        target = "publish" if row["category"]=="publish" else "draft"
        response = session.put(url,json={"status":target},timeout=(8,30))
        item = engine.ns["comprobar_respuesta"](response,endpoint)
        if item.get("id")==rid and item.get("status")==target:
            return "published_remote" if target=="publish" else "drafted"
        return "uncertain"
    except Exception as exc:
        # StoreSession raises before returning an HTTP error; abort on credential loss.
        if any(code in str(exc) for code in ("HTTP 401","HTTP 403")):
            raise ValueError("WooCommerce rechazó la autorización.") from None
        from .woocommerce_export import safe_error
        row["detail"]=safe_error(exc)[:240]
        return "uncertain"


def save_results(batch,job,counts):
    if not batch:
        return
    with transaction() as db:
        for row,outcome in batch:
            category = row["category"]
            audit(db,job["tenant_id"],job["actor"],"woocommerce.reconcile.item",row["local"],
                  after={"job":job["id"],"sku":row["sku"],"category":category,"remote":row["remote"],"detail":row.get("detail")},
                  result=outcome)
            counts[outcome] += 1
    if batch:
        queue.checkpoint(job["id"],job["_owner"],updates={"in_flight":None,"counts":dict(counts)})
