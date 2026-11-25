"""Preview and apply managed catalog changes on the existing queue."""
from collections import Counter
from contextlib import closing
import json
import re
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
ELIGIBLE = {"remove","publish_local","unpublish_local"}
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
            if p.status=="deleted":
                dbi.execute("INSERT INTO lifetime VALUES(?,?,NULL)",(p.id,p.created_at.isoformat()))
        for pid,sku,stamp in stream(db,select(AuditLog.product_id,AuditLog.before["sku"].as_string(),
            AuditLog.created_at).where(AuditLog.tenant_id==tenant,AuditLog.action=="product.deleted")):
            dbi.execute("UPDATE local SET sku=?,display=? WHERE id=? AND status='deleted'",(norm(sku),sku,pid))
            dbi.execute("UPDATE lifetime SET stop=? WHERE local=?",(stamp.isoformat(),pid))
        for pid,rid,parent in stream(db,select(IntegrationMapping.internal_product_id,
            IntegrationMapping.external_id,IntegrationMapping.parent_external_id).where(
                IntegrationMapping.tenant_id==tenant,IntegrationMapping.provider=="woocommerce")):
            dbi.execute("INSERT INTO mapping VALUES(?,?,?)",(pid,rid,parent or 0))
        for stamp,effects in stream(db,select(GenerationJob.created_at,GenerationJob.payload["remote_effects"])
                .where(GenerationJob.kind=="woocommerce_export",GenerationJob.tenant_id==tenant,
                       GenerationJob.payload["store_url"].as_string()==origin)):
            for e in effects or ():
                path = re.fullmatch(r"/wp-json/wc/v3/products(?:/(\d+)/variations)?",e.get("endpoint",""))
                if path and e.get("method")=="POST" and e.get("sku") and type(e.get("id")) is int:
                    dbi.execute("INSERT INTO proof VALUES(?,?,?,?)",(e["id"],int(path[1] or 0),
                        norm(e["sku"]),stamp.isoformat()))
    if not dbi.execute("SELECT 1 FROM local LIMIT 1").fetchone():
        raise ValueError("El inventario validado está vacío. Comprueba la carpeta y la sincronización de Sheets.")


def page_key(run, page):
    return f"rincon:wc-reconcile:{run}:{page}"


def read_page(run,page):
    raw = connection().get(page_key(run,page))
    if raw is None:
        raise ValueError("La vista previa expiró. Genera una nueva.")
    return json.loads(raw)


def result_view(row):
    return {k:row[k] for k in ("key","sku","category","remote_status")}


def process(job, owner):
    job["_owner"] = owner
    payload = job["payload"]
    origin = store_url()
    if payload["store"] != origin:
        raise ValueError("Cambió la tienda. Genera otra vista previa.")
    require_role({"email":job["actor"]},"admin")
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
    dbi.execute("CREATE TABLE current(key TEXT PRIMARY KEY)")
    for row in index.rows():
        checkpoint()
        if row["category"] in ELIGIBLE:
            dbi.execute("INSERT INTO current VALUES(?)",(row["key"],))
    total = dbi.execute("SELECT count(*) FROM approved").fetchone()[0]
    batch = []
    for key,data,current in dbi.execute("SELECT a.key,a.data,c.key FROM approved a LEFT JOIN current c ON c.key=a.key"):
        checkpoint()
        row = json.loads(data)
        outcome = "changed" if current else "stale"
        if current and row["category"]=="remove":
            checkpoint(True)
            outcome = draft(engine,row,job)
        batch.append((row,outcome))
        if len(batch)>=PAGE or row["category"]=="remove":
            save_results(batch,job,counts)
            batch.clear()
            if total and row["category"]!="remove":
                queue.checkpoint(job["id"],job["_owner"],progress=40+int(59*sum(counts.values())/total),
                                 updates={"counts":dict(counts)})
    save_results(batch,job,counts)
    queue.checkpoint(job["id"],job["_owner"],updates={"counts":dict(counts)},progress=99)


def draft(engine,row,job):
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
        if not local or tuple(local)!=("deleted",row["version"]) or reused:
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
        or norm(current.get("global_unique_id"))!=row["barcode"] or current.get("parent_id",0)!=parent
        or (not parent and current.get("type")!=row["kind"])
        or current.get("status")!=row["remote_status"]):
        return "stale"
    if row["kind"]=="variable":
        expected = current.get("variations")
        if not isinstance(expected,list) or len(set(expected))!=len(expected):
            raise ValueError("La tienda devolvió una familia incompleta.")
        remaining = set(expected)
        def children():
            for child in pages(engine,endpoint+"/variations",lambda:queue.checkpoint(job["id"],job["_owner"])):
                if child["id"] not in remaining or child.get("parent_id")!=rid:
                    raise ValueError("La familia cambió. Actualiza la vista previa.")
                remaining.remove(child["id"])
                yield child["id"],norm(child["sku"]),norm(child.get("global_unique_id")),child["status"]
        if family_digest(children())!=row["family"] or remaining:
            return "stale"
    require_role({"email":job["actor"]},"admin")
    queue.checkpoint(job["id"],job["_owner"],updates={"in_flight":{"sku":row["sku"],"remote":rid}})
    try:
        response = session.put(url,json={"status":"draft"},timeout=(8,30))
        item = engine.ns["comprobar_respuesta"](response,endpoint)
        if item.get("id")==rid and item.get("status")=="draft":
            return "changed"
        return "uncertain"
    except Exception as exc:
        # StoreSession raises before returning an HTTP error; abort on credential loss.
        if any(code in str(exc) for code in ("HTTP 401","HTTP 403")):
            raise ValueError("WooCommerce rechazó la autorización.") from None
        return "uncertain"


def save_results(batch,job,counts):
    if not batch:
        return
    with transaction() as db:
        for row,outcome in batch:
            category = row["category"]
            if outcome=="changed" and category!="remove":
                changed = db.execute(update(Product).where(Product.tenant_id==job["tenant_id"],
                    Product.id==row["local"],Product.version==row["version"],
                    Product.status.notin_(["archived","deleted"])).values(
                        status="published" if category=="publish_local" else "pending",
                        version=Product.version+1))
                if not changed.rowcount:
                    outcome="stale"
            audit(db,job["tenant_id"],job["actor"],"woocommerce.reconcile.item",row["local"],
                  after={"job":job["id"],"sku":row["sku"],"category":category,"remote":row["remote"]},
                  result=outcome)
            counts[outcome] += 1
    if any(row["category"]=="remove" for row,_ in batch):
        queue.checkpoint(job["id"],job["_owner"],updates={"in_flight":None,"counts":dict(counts)})
