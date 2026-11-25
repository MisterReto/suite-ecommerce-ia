"""Comparison safety and end-to-end preview/confirmation using synthetic catalogs."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from catalog_platform import reconciliation_api as api, woocommerce_reconciliation as rec
from catalog_platform.database import engine_for, transaction
from catalog_platform.models import AuditLog, Base, GenerationJob, Product, uid
from catalog_platform.reconciliation_index import CatalogIndex
from catalog_platform.reconciliation_store import pages, snapshot


def product(i,sku,kind="simple",parent=0,status="publish"):
    return {"id":i,"sku":sku,"type":kind,"parent_id":parent,"status":status,"variations":[]}


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
    p["variations"]=[2,3]
    shop=Shop([p,product(4,"D"),product(5," d "),product(6,"outside")],
              {1:[product(2,"V","variation",1),product(3,"bad","variation",1)]})
    for row in [("f","f","","variable",None,"published",1,"F"),
                ("v","v","","variation","f","deleted",2,"V"),
                ("o","bad","","variation","absent","pending",1,"bad"),
                ("d","d","","simple",None,"published",1,"D"),
                ("m","missing","","simple",None,"pending",1,"Missing")]:
        index.db.execute("INSERT INTO local VALUES(?,?,?,?,?,?,?,?)",row)
    index.db.execute("INSERT INTO lifetime VALUES('v','1','3')")
    index.db.execute("INSERT INTO proof VALUES(2,1,'v','2')")
    assert snapshot(shop,index,lambda:None)==6
    assert Counter(r["category"] for r in index.rows())=={
        "match":1,"remove":1,"orphan":1,"conflict":2,"independent":1,"missing":1}
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


def test_preview_apply_retry_and_admin_scope(tmp_path,monkeypatch):
    tenant="test-catalog"
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
    monkeypatch.setattr(rec.queue,"available",lambda db:True)
    monkeypatch.setattr(rec.queue,"dispatch",lambda db,job:db.flush())
    shop=Shop([product(i,str(i)) for i in range(1,306)])
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
    assert scanned["counts"]=={"publish_local":1,"remove":1,"independent":303}
    assert len(scanned["rows"])==50 and scanned["more"] and not shop.writes
    with pytest.raises(HTTPException):
        api.apply(preview["id"],api.Approval(confirm=False,all=True),admin)
    approved=api.Approval(confirm=True,all=True)
    applied=api.apply(preview["id"],approved,admin)
    run(applied)
    assert shop.writes==[("2",{"status":"draft"})]
    assert api.apply(preview["id"],approved,admin)["id"]==applied["id"]
    assert api.details(applied["id"],0,admin)["counts"]=={"changed":2}
    again=api.preview(admin)
    run(again)
    assert api.details(again["id"],0,admin)["counts"]=={"match":1,"retired":1,"independent":303}
    with transaction() as db:
        assert db.scalar(select(Product.status).where(Product.sku=="1"))=="published"
    cancelled=api.preview(admin)
    assert api.cancel(cancelled["id"],admin)["status"]=="cancelled"
    assert rec.queue.claim("test",cancelled["id"]) is None
