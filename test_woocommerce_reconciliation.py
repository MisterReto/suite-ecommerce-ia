"""Comparison safety and end-to-end preview/confirmation using synthetic catalogs."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from catalog_platform import reconciliation_api as api, woocommerce_reconciliation as rec
from catalog_platform.database import engine_for, transaction
from catalog_platform.models import AuditLog, Base, GenerationJob, Product, uid
from catalog_platform.reconciliation_index import CatalogIndex
from catalog_platform.reconciliation_store import pages, snapshot
from test_woocommerce_colab import source, store


def product(i,sku,kind="simple",parent=0,status="publish"):
    return {"id":i,"sku":sku,"type":kind,"parent_id":parent,"status":status,"variations":[]}


def test_create_uses_existing_uploader_and_verifies_remote_id(tmp_path,monkeypatch,store):
    import os
    monkeypatch.setenv("DATABASE_URL","sqlite:///"+str(tmp_path/"publish.db"))
    monkeypatch.setenv("APP_ENV","test")
    monkeypatch.setenv("APP_ROLE_MAP",'{"admin@test.local":"admin"}')
    Base.metadata.create_all(engine_for(os.environ["DATABASE_URL"]))
    monkeypatch.setattr(rec.queue,"checkpoint",lambda *args,**kwargs:None)
    with transaction() as db:
        p=Product(tenant_id="shared",sku="S1",name="Ramen")
        db.add(p)
        db.flush()
        row={"sku":"S1","local":p.id,"version":p.version,"kind":"simple"}
    data=source()
    data["ARCHIVOS"]=[]
    engine=rec.Exporter(data,write=True)
    index=CatalogIndex(tmp_path/"index.db")
    index.db.execute("CREATE TABLE created(id INTEGER PRIMARY KEY)")
    job={"tenant_id":"shared","actor":"admin@test.local","id":"test","_owner":"worker"}
    try:
        assert rec.create_remote(engine,row,job,index.db)=="created",row
        assert row["remote"]==store[1]["S1"]["id"]
        assert store[1]["S1"]["status"]=="publish"
        assert rec.create_remote(engine,row,job,index.db)=="skipped"
        assert sum(c["method"]=="POST" and c["endpoint"]=="wc/v3/products" for c in store[0])==1
    finally:
        index.db.close()
        engine.close()


class Shop:
    def __init__(self,items,children=None):
        self.items=items
        self.children=children or {}
        self.writes=[]
        self.ns={"wc_session":self,"WC_API":"https://store.test/wp-json/wc/v3",
                 "comprobar_respuesta":lambda response,endpoint:response.data}

    def mount(self,*args):
        pass

    def close(self):
        pass

    def get(self,url,params,timeout):
        if "page" not in params:
            item=next(x for x in self.items if x["id"]==int(url.split("/")[-1]))
            return SimpleNamespace(data=item)
        rows=self.items if url.endswith("/products") else self.children[int(url.split("/")[-2])]
        page,size=params["page"],params["per_page"]
        return SimpleNamespace(data=rows[(page-1)*size:page*size],
            headers={"X-WP-Total":str(len(rows)),"X-WP-TotalPages":str((len(rows)+size-1)//size)})

    def put(self,url,json,timeout):
        item=next(x for x in self.items if x["id"]==int(url.split("/")[-1]))
        self.writes.append((item["sku"],dict(json)))
        item.update(json)
        return SimpleNamespace(data=item)


def test_families_orphans_duplicates_and_missing(tmp_path):
    index=CatalogIndex(tmp_path/"index.db")
    p=product(1,"F","variable")
    p["variations"]=[2]  # Nested endpoint also returns children omitted by the parent projection.
    shop=Shop([p,product(4,"D"),product(5," d "),product(6,"outside")],
              {1:[product(2,"V","variation",1),product(3,"bad","variation",1)]})
    del shop.children[1][0]["parent_id"]
    for row in [("f","f","","variable",None,"published",1,"F"),
                ("v","v","","variation","f","deleted",2,"V"),
                ("o","bad","","variation","absent","pending",1,"bad"),
                ("d","d","","simple",None,"published",1,"D"),
                ("m","missing","","simple",None,"pending",1,"Missing")]:
        index.db.execute("INSERT INTO local VALUES(?,?,?,?,?,?,?,?)",row)


    assert snapshot(shop,index,lambda:None)==6
    assert Counter(r["category"] for r in index.rows())=={
        "match":1,"remove":2,"orphan":1,"conflict":2,"missing":1}
    index.db.close()


@pytest.mark.parametrize("fault",["headers","short","repeat","auth","interruption"])
def test_invalid_pages_abort(fault):
    shop=Shop([product(i,str(i)) for i in range(1,305)])
    original=shop.get
    def get(url,params,timeout):
        response=original(url,params,timeout)
        if params["page"]==2:
            if fault=="headers": response.headers={}
            if fault=="short": response.data.pop()
            if fault=="repeat": response.data[0]=product(1,"1")
            if fault=="auth": raise ValueError("HTTP 401")
            if fault=="interruption": raise ConnectionError()
        return response
    shop.get=get
    with pytest.raises((ValueError,ConnectionError)):
        list(pages(shop,"products",lambda:None))
    assert not shop.writes


def test_deleted_products_are_proposed_even_without_creation_history(tmp_path):
    index=CatalogIndex(tmp_path/"owner.db")
    for pid in ("a","b"):
        index.db.execute("INSERT INTO local VALUES(?,?,?,?,?,?,?,?)",
            (pid,pid,"","simple",None,"deleted",2,pid))


    index.db.execute("INSERT INTO mapping VALUES('b',2,0)")  # A link alone cannot establish ownership.
    snapshot(Shop([product(1,"a"),product(2,"b")]),index,lambda:None)
    assert [r["category"] for r in index.rows()]==["remove","remove"]
    index.db.close()


def test_preview_apply_retry_and_admin_scope(tmp_path,monkeypatch):
    tenant="test-catalog"
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID",tenant)
    admin={"platform_tenant":tenant,"email":"admin@test.local"}
    monkeypatch.setenv("DATABASE_URL","sqlite:///"+str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("APP_ENV","test")
    monkeypatch.setenv("APP_ROLE_MAP",'{"admin@test.local":"admin","viewer@test.local":"viewer"}')
    monkeypatch.setenv("WC_URL","https://store.test")
    monkeypatch.setenv("WOOCOMMERCE_ALLOWED_HOSTS","store.test")
    monkeypatch.setenv("WC_CONSUMER_KEY","test-key")
    monkeypatch.setenv("WC_CONSUMER_SECRET","test-secret")
    import os
    Base.metadata.create_all(engine_for(os.environ["DATABASE_URL"]))
    index=CatalogIndex(tmp_path/"empty.db")
    with pytest.raises(ValueError,match="vacío"):
        rec.local_snapshot(index,tenant,"https://store.test")
    index.db.close()
    monkeypatch.setattr(rec.queue,"available",lambda db:True)
    monkeypatch.setattr(rec.queue,"dispatch",lambda db,job:db.flush())
    shop=Shop([product(i,str(i),status="draft" if i==1 else "publish") for i in range(1,306)])
    monkeypatch.setattr(rec,"Exporter",lambda **kwargs:shop)
    cache={}
    monkeypatch.setattr(rec,"connection",lambda:SimpleNamespace(
        get=cache.get,setex=lambda key,ttl,value:cache.update({key:value})))
    now=datetime.now(timezone.utc)
    with transaction() as db:
        active=Product(tenant_id=tenant,sku="1",name="Actual")
        deleted=Product(tenant_id=tenant,sku="deleted_test",status="deleted",name="Baja",
                        created_at=now-timedelta(days=3))
        db.add_all([active,deleted])
        db.flush()
        db.add(AuditLog(tenant_id=tenant,actor=admin["email"],action="product.deleted",
                        product_id=deleted.id,before={"sku":"2"},created_at=now))
        db.add(GenerationJob(tenant_id=tenant,actor=admin["email"],request_key=uid(),kind="woocommerce_export",
            created_at=now-timedelta(days=1),status="completed",payload={"store_url":"https://store.test",
            "remote_effects":[{"method":"POST","endpoint":"/wp-json/wc/v3/products","sku":"2","id":2}]}))
    def run(job):
        claimed=rec.queue.claim("test",job["id"])
        assert rec.process(claimed,"test")
        rec.queue.finish(job["id"],"test",True,"Completado")
    with pytest.raises(HTTPException) as denied:
        api.preview({**admin,"email":"viewer@test.local"})
    assert denied.value.status_code==403
    preview=api.preview(admin)
    assert api.preview(admin)["id"]==preview["id"]
    run(preview)
    scanned=api.details(preview["id"],0,admin)
    assert scanned["counts"]=={"publish":1,"remove":304}
    assert len(scanned["rows"])==50 and scanned["more"] and not shop.writes
    with pytest.raises(HTTPException):
        api.apply(preview["id"],api.Approval(confirm=False,all=True),admin)
    approved=api.Approval(confirm=True,keys=[r["key"] for r in scanned["rows"][:3]])
    applied=api.apply(preview["id"],approved,admin)
    run(applied)
    assert sorted(shop.writes,key=lambda x:x[0])==[("1",{"status":"publish"}),("2",{"status":"draft"}),("3",{"status":"draft"})]
    assert api.apply(preview["id"],approved,admin)["id"]==applied["id"]
    assert api.details(applied["id"],0,admin)["counts"]=={"published_remote":1,"drafted":2}
    assert api.latest(admin)["last_sync"]
    again=api.preview(admin)
    run(again)
    assert api.details(again["id"],0,admin)["counts"]=={"match":1,"retired":2,"remove":302}
    with transaction() as db:
        assert db.scalar(select(Product.status).where(Product.sku=="1"))=="pending"
    cancelled=api.preview(admin)
    assert api.cancel(cancelled["id"],admin)["status"]=="cancelled"
    assert rec.queue.claim("test",cancelled["id"]) is None
    # Losing a lease during apply requires a fresh preview, including after some successful writes.
    with transaction() as db:
        lost=GenerationJob(tenant_id=tenant,actor=admin["email"],request_key=uid(),kind=rec.KIND,
            status="processing",lease_owner="gone",lease_until=1,payload={"preview":again["id"]})
        db.add(lost)
        db.flush()
        rec.queue.recover_expired(db,lost.id)
        assert lost.status=="failed" and lost.lease_owner is None
