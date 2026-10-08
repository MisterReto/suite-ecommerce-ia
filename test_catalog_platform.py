"""HTTP, persistent queue and accepted generator regression; no live API spend.
TEST_DATABASE_URL enables the same cases on the dedicated CI PostgreSQL service.
"""
import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import time
from unittest.mock import Mock
os.environ.setdefault("GOOGLE_CLIENT_ID","test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET","test")
os.environ.setdefault("GOOGLE_REDIRECT_URI","https://suite.example/auth/callback")
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image,ImageDraw
from sqlalchemy import select,func
import studio_api as studio
import service_entrypoint
from catalog_platform.database import engine_for,transaction
from catalog_platform.models import Base,Product,ProductImage,GenerationJob,GeneratedAsset,InventoryMovement,IntegrationAccount,WebhookEvent,AuditLog,WorkerHeartbeat,uid
from catalog_platform import queue,worker
from catalog_platform.security import unseal
from creative_pipeline import fallback_brief,IMAGE_MODEL
from ecommerce_services import WooCommerceService

ORIGIN={"Origin":"https://suite.example"}

class DriveDouble:
    def __init__(self,root): self.root_id=root;self.files={};self.uploads=[]
    def download(self,key): return self.files[key]
    def working_folder(self,*parts): return "/".join(parts)
    def folder(self,name,parent=None): return (parent + "/" if parent else "") + name
    def upload(self,path,name,folder,properties=None):
        raw=Path(path).read_bytes();key=uid();self.files[key]=raw
        self.uploads.append({"id":key,"name":name,"folder":folder,"properties":properties,"raw":raw})
        return {"id":key,"name":name}
    def upload_bytes(self,data,name,folder,mime_type):
        key=uid();self.files[key]=data;return {"id":key}

@pytest.fixture
def setup(tmp_path,monkeypatch):
    url=os.getenv("TEST_DATABASE_URL") or "sqlite:///"+str(tmp_path/"platform.db")
    monkeypatch.setenv("DATABASE_URL",url);monkeypatch.setenv("APP_ENV","test")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY",Fernet.generate_key().decode())
    monkeypatch.setenv("RENDER_EXTERNAL_URL","https://suite.example")
    monkeypatch.setenv("APP_ROLE_MAP",json.dumps({"admin@example.test":"admin","editor@example.test":"editor","viewer@example.test":"viewer"}))
    monkeypatch.setenv("STOCK_AUTHORITY","app")
    Base.metadata.create_all(engine_for(url))
    tenant="test_"+secrets.token_hex(12);sid=secrets.token_urlsafe(24)
    value={"session_id":sid,"email":"admin@example.test","expires_at":time.time()+600,
        "file_namespace":secrets.token_urlsafe(24),"platform_tenant":tenant,"carpeta_raiz_id_manual":tenant,
        "gemini_key":"test-key-no-spend","creds":{"token":"private-token","refresh_token":"private-refresh"}}
    studio.runtime.SESSIONS[sid]=value
    from catalog_platform.accounts import save_gemini
    with transaction() as db:
        save_gemini(db, tenant, value["email"], value["gemini_key"])
    drive=DriveDouble(tenant)
    from drive_service import DriveService
    monkeypatch.setattr(DriveService,"for_session",lambda *args:drive)
    client=TestClient(service_entrypoint.fastapi_app,base_url="https://suite.example");client.cookies.set("session_id",sid)
    yield client,value,drive
    with transaction() as db:
        for job in db.scalars(select(GenerationJob).where(GenerationJob.tenant_id==tenant,GenerationJob.status.in_(["queued","processing"]))): job.status="completed"
        for beat in db.scalars(select(WorkerHeartbeat)): beat.updated=0
    studio.runtime._eliminar_sesion(sid);client.close()


def create(client,**overrides):
    data={"sku":"POCK41","name":"Pocky chocolate","brand":"Glico","category":"Dulces","price":35,"stock":10,**overrides}
    result=client.post("/api/platform/products",json=data,headers=ORIGIN)
    assert result.status_code==201,result.text
    return result.json()["product"]


def reference(client,product):
    image=Image.new("RGB",(120,180),"orange");buf=io.BytesIO();image.save(buf,"PNG")
    up=client.post("/api/uploads",files={"image":("pocky.png",buf.getvalue(),"image/png")},headers=ORIGIN)
    result=client.post(f"/api/platform/products/{product['id']}/reference",json={"upload_id":up.json()["id"]},headers=ORIGIN)
    assert result.status_code==200,result.text
    return result.json()["image"]


def enqueue(client,value,product,slots=None,quantity=1,key=None):
    queue.heartbeat("test_"+value["platform_tenant"])
    data={"product_ids":[product["id"]],"slots":slots or ["1_hd","2_uso","3_comercial"],"quantity":quantity}
    quote=client.post("/api/platform/generation/estimate",json=data,headers=ORIGIN)
    assert quote.status_code==200,quote.text
    response=client.post("/api/platform/generation/jobs",json={**data,"request_key":key or uid(),"confirm":True,"estimate_token":quote.json()["estimate_token"]},headers=ORIGIN)
    assert response.status_code==202,response.text
    return response.json()["jobs"][0],quote.json()


def fake_provider(monkeypatch):
    image=Image.new("RGB",(1024,1024),"purple");ImageDraw.Draw(image).rectangle((360,140,664,940),fill="orange")
    maker=Mock(return_value=image);planner=Mock(side_effect=lambda client,p,paths:fallback_brief(p))
    monkeypatch.setattr(studio,"generate",maker);monkeypatch.setattr(studio,"brief",planner)
    monkeypatch.setattr(studio,"load_style_examples",lambda *args:([],""))
    import creative_pipeline
    monkeypatch.setattr(creative_pipeline,"load_style_examples",lambda *args:([],""))
    return maker,planner


def execute(job,value,drive):
    claimed=queue.claim(worker.OWNER);assert claimed["id"]==job["id"]
    assert worker.generation(claimed,value,drive)
    queue.finish(job["id"],worker.OWNER,True,"Completado")
    return claimed


def test_auth_roles_and_tenant_isolation(setup):
    client,value,_=setup
    product=create(client)
    assert client.get("/api/platform/products?q=Pocky").json()["items"][0]["id"]==product["id"]
    assert client.get("/api/platform/products?q=POCK41").json()["total"]==1
    value["platform_tenant"]="other_"+uid()
    assert client.get("/api/platform/products").json()["total"]==0
    assert client.get("/api/platform/products/"+product["id"]).status_code==404
    value["email"]="viewer@example.test"
    assert client.post("/api/platform/products",json={"sku":"X","name":"X"},headers=ORIGIN).status_code==403
    assert client.post("/api/settings",json={"api_key":"A"*25},headers=ORIGIN).status_code==403
    assert client.get("/api/platform/status").json()["role"]=="viewer"
    client.cookies.clear()
    assert client.get("/api/platform/products").status_code==401


def test_versions_stock_events_and_full_families(setup):
    client,value,_=setup
    p=create(client)
    change={"quantity":8,"event_id":uid(),"version":p["version"],"reason":"Conteo físico"}
    url=f"/api/platform/products/{p['id']}/stock"
    assert client.post(url,json=change,headers=ORIGIN).status_code==200
    assert client.post(url,json=change,headers=ORIGIN).status_code==200
    assert client.post(url,json={**change,"event_id":uid()},headers=ORIGIN).status_code==409
    with transaction() as db:
        movements=list(db.scalars(select(InventoryMovement).where(InventoryMovement.product_id==p["id"])))
        assert len(movements)==2 # initial + one physical count
        assert movements[-1].quantity_before==10 and movements[-1].delta==-2
    assert client.put(f"/api/platform/products/{p['id']}",json={**p,"name":"Cambio obsoleto"},headers=ORIGIN).status_code==409
    parent=create(client,sku="POCKFULL",product_type="variable",price=100,stock=300)
    assert parent["stock"] is None and parent["price"] is None
    child=create(client,sku="POCK75",product_type="variation",parent_id=parent["id"],attributes={"Tamaño":"75 g"})
    assert client.get(f"/api/platform/products/{parent['id']}").json()["variants"][0]["id"]==child["id"]
    assert client.put(f"/api/platform/products/{parent['id']}",json={**parent,"product_type":"simple"},headers=ORIGIN).status_code==422


def test_quote_changes_no_worker_and_replay(setup):
    client,value,_=setup
    p=create(client);reference(client,p)
    data={"product_ids":[p["id"]],"slots":["1_hd"],"quantity":2}
    quote=client.post("/api/platform/generation/estimate",json=data,headers=ORIGIN).json()
    assert quote["images"]==2 and quote["provider"]=="gemini" and quote["model"]==IMAGE_MODEL
    request={**data,"request_key":uid(),"confirm":True,"estimate_token":quote["estimate_token"]}
    assert client.post("/api/platform/generation/jobs",json=request,headers=ORIGIN).status_code==503
    queue.heartbeat("test_"+value["platform_tenant"])
    assert client.post("/api/platform/generation/jobs",json={**request,"confirm":False},headers=ORIGIN).status_code==422
    assert client.post("/api/platform/generation/jobs",json={**request,"quantity":3},headers=ORIGIN).status_code==409
    accepted=client.post("/api/platform/generation/jobs",json=request,headers=ORIGIN)
    replay=client.post("/api/platform/generation/jobs",json=request,headers=ORIGIN)
    assert accepted.status_code==202 and replay.status_code==202
    assert accepted.json()["jobs"][0]["id"]==replay.json()["jobs"][0]["id"]
    with transaction() as db:
        account=db.scalar(select(IntegrationAccount).where(IntegrationAccount.tenant_id==value["platform_tenant"], IntegrationAccount.provider=="studio"))
        assert "private-token" not in account.encrypted_credentials
        assert unseal(account.encrypted_credentials)["creds"]["refresh_token"]=="private-refresh"
    assert "private-token" not in client.get("/api/platform/jobs").text
    client.cookies.clear() # the accepted SQL job survives the browser session
    with transaction() as db: assert db.scalar(select(GenerationJob.status).where(GenerationJob.id==accepted.json()["jobs"][0]["id"]))=="queued"


def test_worker_reuses_accepted_pipeline_and_corrects_previous_image(setup,monkeypatch):
    client,value,drive=setup
    p=create(client);original=reference(client,p)
    maker,planner=fake_provider(monkeypatch)
    job,_=enqueue(client,value,p)
    execute(job,value,drive)
    assert maker.call_count==3 and planner.call_count==1
    assets=client.get("/api/platform/assets").json()["items"]
    assert len(assets)==3 and all(a["status"]=="completed" and a["product_id"]==p["id"] and a["job_id"]==job["id"] for a in assets)
    for a in assets:
        record=client.get(f"/api/platform/images/{a['image_id']}")
        assert record.status_code==200 and record.headers["cache-control"]=="no-store"
        with Image.open(io.BytesIO(record.content)) as image: assert image.format=="JPEG" and image.size==(1024,1024)
        assert hashlib.sha256(record.content).hexdigest()==a["metadata_json"]["checksum"]
    assert len(drive.uploads)==7 # original, 3 approved-ready candidates, 3 raw
    chosen=next(a for a in assets if a["slot"]=="2_uso")
    request={"feedback":"Sostener el paquete con la mano derecha","confirm_cost":True,"request_key":uid()}
    response=client.post(f"/api/platform/assets/{chosen['id']}/correct",json=request,headers=ORIGIN)
    assert response.status_code==202,response.text
    correction=response.json()["job"];execute(correction,value,drive)
    assert maker.call_count==4 and planner.call_count==1
    assert Path(maker.call_args.kwargs["previous"]).read_bytes()==drive.files[chosen["raw_drive_file_id"]]
    assert "mano derecha" in maker.call_args.kwargs["corrections"][0]
    assert Path(maker.call_args.args[1][0]).read_bytes()==drive.files[original["drive_file_id"]]
    assert len(client.get("/api/platform/assets").json()["items"])==4
    # Completed image checkpoints do not initiate another paid call.
    with transaction() as db: saved=db.get(GenerationJob,job["id"]);saved.status="queued"
    execute(job,value,drive)
    assert maker.call_count==4


def test_review_then_publish_and_editor_cannot_publish(setup,monkeypatch):
    client,value,drive=setup
    p=create(client);reference(client,p);fake_provider(monkeypatch)
    job,_=enqueue(client,value,p,slots=["1_hd"]);execute(job,value,drive)
    publish=f"/api/platform/products/{p['id']}/publish"
    assert client.post(publish,json={"confirm":True,"request_key":uid()},headers=ORIGIN).status_code==422
    asset=client.get("/api/platform/assets").json()["items"][0]
    assert client.post(f"/api/platform/assets/{asset['id']}/review",json={"status":"approved","role":"main"},headers=ORIGIN).status_code==200
    value["email"]="editor@example.test"
    assert client.post(publish,json={"confirm":True,"request_key":uid()},headers=ORIGIN).status_code==403
    value["email"]="admin@example.test"
    result=client.post(publish,json={"confirm":True,"request_key":uid()},headers=ORIGIN)
    assert result.status_code==202 and result.json()["job"]["kind"]=="publication"
    assert not any(a.get("wordpress_media_id") for a in client.get(f"/api/platform/products/{p['id']}").json()["images"])


def test_restart_safe_checkpoint_and_uncertain_generation_not_repeated(setup):
    client,value,_=setup
    p=create(client)
    with transaction() as db:
        safe=GenerationJob(tenant_id=value["platform_tenant"],actor=value["email"],product_id=p["id"],request_key=uid(),status="processing",lease_owner="old",lease_until=0,payload={"completed_keys":["1_hd:1"]})
        uncertain=GenerationJob(tenant_id=value["platform_tenant"],actor=value["email"],product_id=p["id"],request_key=uid(),status="processing",lease_owner="old",lease_until=0,payload={"in_flight":{"operation":"image_generation"}})
        db.add_all([safe,uncertain]);db.flush();a,b=safe.id,uncertain.id
    resumed=queue.claim("new");assert resumed["id"]==a and resumed["payload"]["completed_keys"]==["1_hd:1"]
    with transaction() as db: assert db.get(GenerationJob,b).status=="failed"
    with pytest.raises(RuntimeError): queue.checkpoint(a,"old",progress=90)
    result=client.post(f"/api/platform/jobs/{b}/retry",json={"request_key":uid(),"confirm":True},headers=ORIGIN)
    assert result.status_code==422


def test_signed_webhooks_duplicates_and_out_of_order_stock(setup,monkeypatch):
    client,value,_=setup
    monkeypatch.setenv("WOOCOMMERCE_WEBHOOK_SECRET","webhook-test-secret");monkeypatch.setenv("WEBHOOK_TENANT_ID",value["platform_tenant"]);monkeypatch.setenv("STOCK_AUTHORITY","woocommerce")
    p=create(client)
    with transaction() as db: db.get(Product,p["id"]).woocommerce_product_id=123
    body=json.dumps({"id":123,"sku":p["sku"],"stock_quantity":7,"date_modified_gmt":"2026-10-06T12:00:00"}).encode()
    signature=base64.b64encode(hmac.new(b"webhook-test-secret",body,hashlib.sha256).digest()).decode()
    headers={"X-WC-Webhook-Signature":signature,"X-WC-Webhook-Delivery-ID":"event-"+uid(),"X-WC-Webhook-Topic":"product.updated"}
    assert client.post("/webhooks/woocommerce",content=body).status_code==401
    first=client.post("/webhooks/woocommerce",content=body,headers=headers)
    second=client.post("/webhooks/woocommerce",content=body,headers=headers)
    assert first.status_code==202 and second.json()["duplicate"]
    renamed=client.post("/webhooks/woocommerce",content=body,headers={**headers,"X-WC-Webhook-Delivery-ID":"other-"+uid()})
    assert renamed.json()["duplicate"] # same signed body cannot replay under an unsigned new delivery ID
    claimed=queue.claim(worker.OWNER);assert claimed["kind"]=="webhook"
    from catalog_platform.webhooks import process_event
    assert process_event(claimed,worker.OWNER);assert process_event(claimed,worker.OWNER)
    with transaction() as db:
        product=db.get(Product,p["id"]);assert product.stock==7
        assert db.scalar(select(func.count()).select_from(WebhookEvent).where(WebhookEvent.tenant_id==value["platform_tenant"]))==1
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id==p["id"],InventoryMovement.source=="woocommerce"))==1
        from catalog_platform.ecommerce import apply_snapshot
        assert apply_snapshot(db,product,{"sku":p["sku"],"stock_quantity":99,"date_modified_gmt":"2026-10-05T12:00:00"},"old",value["email"]) is False
        assert product.stock==7
    changed=body.replace(b'7,',b'6,');sig=base64.b64encode(hmac.new(b"webhook-test-secret",changed,hashlib.sha256).digest()).decode()
    assert client.post("/webhooks/woocommerce",content=changed,headers={**headers,"X-WC-Webhook-Signature":sig}).status_code==409


def test_import_export_roundtrip_keeps_tags_attributes_and_formula_safe(setup):
    client,value,_=setup
    p=create(client,name="=Formula",tags=["Dulces","Chocolate"],attributes={"Tamaño":"41 g"})
    from catalog_platform.imports import parse_file
    for fmt in ["csv","xlsx"]:
        response=client.get("/api/platform/export?format="+fmt)
        rows,errors=parse_file("catalog."+fmt,response.content)
        assert not errors and rows[0]["sku"]==p["sku"]
        assert rows[0]["tags"]==p["tags"] and rows[0]["attributes"]==p["attributes"]
        assert rows[0]["name"].startswith("'")


def test_permanent_mapping_never_searches_sku_again_or_writes_wrong_id():
    client=Mock();service=WooCommerceService(client)
    p=Product(id=uid(),tenant_id="test",sku="POCK41",woocommerce_product_id=123)
    client.request.return_value={"id":123,"sku":"POCK41"}
    assert service.resolve(p)["id"]==123
    client.find_entity_by_sku.assert_not_called()
    client.request.return_value={"id":123,"sku":"OTHER"}
    with pytest.raises(ValueError): service.resolve(p)
    client.update_product.assert_not_called()


def test_worker_publication_reuses_wordpress_ids_and_verifies_mapping(setup,monkeypatch):
    client,value,drive=setup
    p=create(client);reference(client,p);fake_provider(monkeypatch)
    job,_=enqueue(client,value,p,slots=["1_hd"]);execute(job,value,drive)
    a=client.get("/api/platform/assets").json()["items"][0]
    client.post(f"/api/platform/assets/{a['id']}/review",json={"status":"approved","role":"main"},headers=ORIGIN)
    media=Mock();media.upload.return_value={"id":456,"source_url":"https://store.example/pocky.jpg"}
    woo=Mock();woo.publish.return_value={"id":123};woo.product.return_value={"id":123,"sku":p["sku"],"status":"publish"}
    import ecommerce_services,woocommerce_product_sync
    monkeypatch.setattr(ecommerce_services,"WordPressMediaService",lambda:media)
    monkeypatch.setattr(ecommerce_services,"WooCommerceService",lambda:woo)
    monkeypatch.setattr(woocommerce_product_sync,"resolve_taxonomies",lambda *args:{})
    for _ in range(2):
        response=client.post(f"/api/platform/products/{p['id']}/publish",json={"confirm":True,"request_key":uid()},headers=ORIGIN)
        assert response.status_code==202,response.text
        pending=queue.claim(worker.OWNER)
        assert worker.publication(pending,value,drive)
        queue.finish(pending["id"],worker.OWNER,True,"Publicación verificada")
    media.upload.assert_called_once();assert woo.publish.call_count==2
    result=client.get(f"/api/platform/products/{p['id']}").json()
    assert result["product"]["woocommerce_product_id"]==123
    assert result["product"]["wordpress_media_ids"]==[456]
    assert result["assets"][0]["status"]=="published"
    assert client.post(f"/api/platform/assets/{a['id']}/review",json={"status":"rejected"},headers=ORIGIN).status_code==409


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),reason="Requires dedicated CI PostgreSQL for actual SKIP LOCKED")
def test_postgres_two_workers_claim_distinct_jobs(setup):
    from concurrent.futures import ThreadPoolExecutor
    client,value,_=setup
    first=create(client);second=create(client,sku="POCK75")
    with transaction() as db:
        for p in (first,second): db.add(GenerationJob(tenant_id=value["platform_tenant"],actor=value["email"],product_id=p["id"],request_key=uid()))
    with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(queue.claim,["worker-A","worker-B"]))
    assert all(results) and results[0]["id"]!=results[1]["id"]
    with transaction() as db:
        assert all(db.get(GenerationJob,r["id"]).status=="processing" for r in results)


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),reason="Requires actual PostgreSQL concurrent submissions")
def test_postgres_duplicate_http_is_one_job(setup):
    from concurrent.futures import ThreadPoolExecutor
    client,value,_=setup
    p=create(client);reference(client,p);queue.heartbeat("test_"+value["platform_tenant"])
    data={"product_ids":[p["id"]],"slots":["1_hd"]}
    quote=client.post("/api/platform/generation/estimate",json=data,headers=ORIGIN).json()
    request={**data,"request_key":uid(),"confirm":True,"estimate_token":quote["estimate_token"]}
    def submit(_):
        with TestClient(service_entrypoint.fastapi_app,base_url="https://suite.example") as second:
            second.cookies.set("session_id",value["session_id"])
            return second.post("/api/platform/generation/jobs",json=request,headers=ORIGIN)
    with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(submit,range(2)))
    assert all(r.status_code==202 for r in results)
    assert results[0].json()["jobs"][0]["id"]==results[1].json()["jobs"][0]["id"]


def test_private_images_and_catalog_are_not_in_pwa_cache(setup):
    client,value,_=setup
    response=client.get("/sw.js")
    if response.status_code==200:
        source=response.text
        assert "request.method !== 'GET'" in source
        assert "url.pathname.startsWith('/_next/static/')" in source
        assert "if (!shell && !asset) return" in source
        assert "'/api/" not in source
        manifest=client.get("/manifest.webmanifest")
        assert manifest.status_code==200 and manifest.json()["display"]=="standalone"
        assert {icon["sizes"] for icon in manifest.json()["icons"]}=={"192x192","512x512"}


def test_loyverse_authority_blocks_stock_edits_in_all_master_forms(setup,monkeypatch):
    client,value,_=setup
    p=create(client)
    monkeypatch.setenv("STOCK_AUTHORITY","loyverse")
    assert client.post(f"/api/platform/products/{p['id']}/stock",json={"quantity":20,"event_id":uid(),"version":p["version"],"reason":"conteo"},headers=ORIGIN).status_code==409
    assert client.put(f"/api/platform/products/{p['id']}",json={**p,"stock":20},headers=ORIGIN).status_code==422
    assert client.post(f"/api/platform/products/{p['id']}/sync-stock",json={"confirm":True,"request_key":uid()},headers=ORIGIN).status_code==409
    assert client.get(f"/api/platform/products/{p['id']}").json()["product"]["stock"]==10


def test_unlisted_google_account_cannot_read_shared_catalog(setup):
    client,value,_=setup
    create(client)
    value["email"]="unlisted@example.test"
    assert client.get("/api/platform/products").status_code==403
    assert client.get("/api/catalog").status_code==403
    assert client.post("/api/generate",json={"slots":["1_hd"]},headers=ORIGIN).status_code==403
    assert client.get("/api/session").status_code==200
