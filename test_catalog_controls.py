"""Deletion/cancellation regressions. Provider and Drive doubles never spend."""
from copy import deepcopy
import os
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from sqlalchemy import select, func

from test_catalog_platform import setup, create, reference, enqueue, fake_provider, ORIGIN
from catalog_platform import queue, worker
from catalog_platform.database import transaction
from catalog_platform.models import Product, ProductImage, GenerationJob, GeneratedAsset, InventoryMovement, AuditLog, uid


def new_job(value, product_id=None, **fields):
    with transaction() as db:
        job = GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"],
                            product_id=product_id, request_key=uid(), **fields)
        db.add(job)
        db.flush()
        return job.id


def stop(client, job_id, **body):
    return client.post(f"/api/platform/jobs/{job_id}/cancel", json={"confirm": True, **body}, headers=ORIGIN)


def remove(client, product, **body):
    return client.request("DELETE", f"/api/platform/products/{product['id']}",
                          json={"confirm": True, "version": product["version"], **body}, headers=ORIGIN)


@pytest.mark.parametrize("kind", ["generation", "studio_generation", "ecommerce_pull"])
def test_cancel_queued_is_durable_without_worker_or_redis(setup, monkeypatch, kind):
    client, value, drive = setup
    job_id = new_job(value, kind=kind)
    remote = Mock(side_effect=AssertionError("Cancellation must not contact a worker/provider"))
    monkeypatch.setattr(queue, "available", remote)
    monkeypatch.setattr(worker, "process", remote)
    assert stop(client, job_id, confirm=False).status_code == 422
    assert stop(client, job_id).json()["job"]["status"] == "cancelled"
    assert stop(client, job_id).json()["job"]["status"] == "cancelled"
    assert queue.claim("test-worker", job_id) is None
    assert worker.execute_job(job_id) == {"executed": False}
    with transaction() as db:
        job = db.get(GenerationJob, job_id)
        assert job.finished_at and not job.lease_owner and not job.lease_until
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.tenant_id == value["platform_tenant"], AuditLog.action == "job.cancel_requested")) == 1
    remote.assert_not_called()
    assert not drive.uploads


def test_cancel_saves_inflight_result_and_never_restarts(setup):
    client, value, _ = setup
    payload = {"in_flight": {"operation": "image_generation"}, "completed_keys": ["1_hd"], "results": {"1_hd": "saved"}}
    job_id = new_job(value, kind="studio_generation", payload=payload)
    assert queue.claim("owner", job_id)
    assert stop(client, job_id).json()["job"]["status"] == "cancelling"
    queue.renew(job_id, "owner")
    with transaction() as db:
        assert db.get(GenerationJob, job_id).status == "cancelling"
    result = {**deepcopy(payload), "in_flight": None, "completed_keys": ["1_hd", "2_uso"], "results": {"1_hd": "saved", "2_uso": "also-saved"}}
    with pytest.raises(queue.JobCancelled):
        queue.checkpoint(job_id, "owner", payload=result, progress=66)
    with transaction() as db:
        saved = db.get(GenerationJob, job_id)
        assert saved.status == "cancelled" and saved.payload == result and saved.progress == 66
    queue.finish(job_id, "owner", False, "Must not become failed")
    assert queue.claim("new-worker", job_id) is None
    assert client.post(f"/api/platform/jobs/{job_id}/retry", json={"confirm": True, "request_key": uid(), "uncertainty_reviewed": True}, headers=ORIGIN).status_code == 422


def test_expired_process_cancels_without_waiting_for_a_sleeping_worker(setup):
    client, value, _ = setup
    job_id = new_job(value, status="processing", lease_owner="lost", lease_until=0,
                     payload={"in_flight": {"operation": "image_generation"}})
    assert stop(client, job_id).json()["job"]["status"] == "cancelled"
    assert queue.claim("new", job_id) is None


def test_worker_does_not_report_requested_stop_as_failure(setup, monkeypatch):
    client, value, _ = setup
    product = create(client)
    job_id = new_job(value, product["id"], kind="stock_sync")
    def interrupted(job):
        assert stop(client, job_id).json()["job"]["status"] == "cancelling"
        raise RuntimeError("In-flight call did not return")
    monkeypatch.setattr(worker, "process", interrupted)
    assert worker.execute_job(job_id) == {"executed": True, "cancelled": True}
    with transaction() as db:
        assert db.get(Product, product["id"]).sync_status == "pending"
        assert db.get(GenerationJob, job_id).status == "cancelled"
        assert not db.scalar(select(AuditLog.id).where(AuditLog.product_id == product["id"], AuditLog.result == "failed"))


def test_cancel_stops_next_paid_call_but_preserves_generated_asset(setup, monkeypatch):
    client, value, drive = setup
    product = create(client)
    reference(client, product)
    maker, _ = fake_provider(monkeypatch)
    job, _ = enqueue(client, value, product, slots=["1_hd"], quantity=3)
    # Cancellation arrives during the first provider call, before it returns.
    def cancel_during_generation(*args, **kwargs):
        assert stop(client, job["id"]).json()["job"]["status"] == "cancelling"
        return maker.return_value
    maker.side_effect = cancel_during_generation
    claimed = queue.claim(worker.OWNER, job["id"])
    with pytest.raises(queue.JobCancelled):
        worker.generation(claimed, value, drive)
    assert maker.call_count == 1
    with transaction() as db:
        saved = db.get(GenerationJob, job["id"])
        assert saved.status == "cancelled" and saved.payload["completed_keys"] == ["1_hd:1"]
        assert not saved.payload["in_flight"]
        assert db.scalar(select(func.count()).select_from(GeneratedAsset).where(GeneratedAsset.job_id == job["id"])) == 1
    assert len(drive.uploads) == 3  # Original plus the completed image and raw.
    asset = client.get("/api/platform/assets").json()["items"][0]
    assert client.post(f"/api/platform/assets/{asset['id']}/review", json={"status": "approved", "role": "main"}, headers=ORIGIN).status_code == 200
    with transaction() as db:
        assert db.get(GenerationJob, job["id"]).status == "cancelled"
    assert remove(client, product).status_code == 200
    assert client.get("/api/platform/assets").json()["items"] == []
    assert client.get("/api/platform/dashboard").json()["stats"]["completed_images"] == 0


@pytest.mark.parametrize("inflight", [None, {"operation": "woocommerce_publish"}])
def test_restart_does_not_requeue_cancellation(setup, inflight):
    client, value, _ = setup
    job_id = new_job(value, kind="publication", status="processing", lease_owner="old", lease_until=time.time()+300,
                     payload={"in_flight": inflight, "completed_keys": ["saved"]})
    assert stop(client, job_id).json()["job"]["status"] == "cancelling"
    with transaction() as db:
        db.get(GenerationJob, job_id).lease_until = 0
    assert queue.claim("new", job_id) is None
    with transaction() as db:
        saved = db.get(GenerationJob, job_id)
        assert saved.status == "cancelled" and saved.payload["in_flight"] == inflight
        assert bool("incierto" in saved.message) == bool(inflight)


def test_stop_all_is_atomic_scoped_and_leaves_new_jobs_alone(setup):
    client, value, _ = setup
    ids = [new_job(value, kind=kind) for kind in ["studio_generation", "ecommerce_pull", "ecommerce_pull"]]
    later = new_job(value, kind="ecommerce_pull")
    assert client.post("/api/platform/jobs/cancel", json={"confirm": True, "job_ids": ids+[uid()]}, headers=ORIGIN).status_code == 404
    with transaction() as db:
        assert all(db.get(GenerationJob, job_id).status == "queued" for job_id in ids)
    result = client.post("/api/platform/jobs/cancel", json={"confirm": True, "job_ids": ids}, headers=ORIGIN)
    assert result.status_code == 200 and all(job["status"] == "cancelled" for job in result.json()["jobs"])
    with transaction() as db:
        assert db.get(GenerationJob, later).status == "queued"


def test_controls_require_session_origin_role_and_own_tenant(setup):
    client, value, _ = setup
    product = create(client)
    job_id = new_job(value)
    assert client.post(f"/api/platform/jobs/{job_id}/cancel", json={"confirm": True}).status_code == 403
    assert client.request("DELETE", f"/api/platform/products/{product['id']}", json={"confirm": True, "version": product["version"]}).status_code == 403
    root = value["platform_tenant"]
    value["platform_tenant"] = "other-"+uid()
    assert stop(client, job_id).status_code == 404 and remove(client, product).status_code == 404
    value["platform_tenant"] = root
    value["email"] = "viewer@example.test"
    assert stop(client, job_id).status_code == 403 and remove(client, product).status_code == 403
    value["email"] = "editor@example.test"
    assert stop(client, job_id).status_code == 403 and remove(client, product).status_code == 403
    own = new_job(value)
    assert client.post("/api/platform/jobs/cancel", json={"confirm": True, "job_ids": [own, job_id]}, headers=ORIGIN).status_code == 403
    with transaction() as db:
        assert db.get(GenerationJob, own).status == "queued"
    assert stop(client, own).status_code == 200
    value["email"] = "admin@example.test"
    cookies = dict(client.cookies)
    client.cookies.clear()
    assert stop(client, job_id).status_code == 401 and remove(client, product).status_code == 401
    client.cookies.update(cookies)


def test_delete_hides_catalog_but_retains_drive_remote_ids_and_history(setup):
    client, value, drive = setup
    product = create(client, barcode="7501055363193", stock=0)
    reference(client, product)
    job_id = new_job(value, product["id"])
    with transaction() as db:
        db.get(Product, product["id"]).woocommerce_product_id = 321
        image_count = db.scalar(select(func.count()).select_from(ProductImage).where(ProductImage.product_id == product["id"]))
        movement_count = db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id == product["id"]))
    files = deepcopy(drive.files)
    assert remove(client, product, confirm=False).status_code == 422
    assert remove(client, product, version=product["version"]+1).status_code == 409
    assert remove(client, product).status_code == 200
    assert remove(client, product).json()["replayed"]
    assert client.get(f"/api/platform/products/{product['id']}").status_code == 404
    for filter_name in ["all", "pending", "out", "low", "error", "difference"]:
        assert client.get("/api/platform/products", params={"filter": filter_name}).json()["total"] == 0
    assert product["sku"] not in client.get("/api/platform/export").text
    assert client.get("/api/platform/dashboard").json()["stats"]["products"] == 0
    from catalog_platform.capture_bridge import master_rows
    assert not master_rows(value)
    with transaction() as db:
        saved = db.get(Product, product["id"])
        assert saved.status == "deleted" and saved.woocommerce_product_id == 321 and saved.stock == 0
        assert db.get(GenerationJob, job_id).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(ProductImage).where(ProductImage.product_id == product["id"])) == image_count
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id == product["id"])) == movement_count
        entry = db.scalar(select(AuditLog).where(AuditLog.product_id == product["id"], AuditLog.action == "product.deleted"))
        assert entry.before["sku"] == product["sku"] and entry.after["scope"] == "app"
    assert drive.files == files
    assert create(client, sku=product["sku"])["id"] != product["id"]


def test_delete_waits_for_process_and_preserves_family(setup):
    client, value, _ = setup
    parent = create(client, sku="750105xxxxxxx", product_type="variable")
    child = create(client, sku="7501055363193", product_type="variation", parent_id=parent["id"])
    assert remove(client, parent).status_code == 409
    job_id = new_job(value, child["id"])
    queue.claim("owner", job_id)
    assert remove(client, child).status_code == 409
    assert stop(client, job_id).json()["job"]["status"] == "cancelling"
    assert remove(client, child).status_code == 409
    with pytest.raises(queue.JobCancelled):
        queue.checkpoint(job_id, "owner", payload={"in_flight": {"operation": "new-call"}})
    assert remove(client, child).status_code == 200
    assert client.get(f"/api/platform/products/{parent['id']}").json()["variants"] == []
    assert remove(client, parent).status_code == 200


def test_refresh_does_not_restore_deleted_remote_product(setup, monkeypatch):
    client, value, drive = setup
    product = create(client)
    with transaction() as db:
        db.get(Product, product["id"]).woocommerce_product_id = 321
    assert remove(client, product).status_code == 200
    woo = Mock()
    woo.orders.return_value = []
    woo.client.list_all_products.return_value = [{"id": 321, "sku": product["sku"]}]
    monkeypatch.setattr("ecommerce_services.WooCommerceService", lambda: woo)
    job_id = new_job(value, kind="ecommerce_pull", payload={"import_products": True})
    claimed = queue.claim("owner", job_id)
    from catalog_platform.ecommerce import refresh
    assert refresh(claimed, "owner", value, drive)
    woo.product.assert_not_called()
    woo.resolve.assert_not_called()
    assert client.get("/api/platform/products").json()["total"] == 0
    queue.finish(job_id, "owner", True, "Read completed")


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires real PostgreSQL row locks")
def test_postgres_cancel_and_claim_never_requeue_or_lose_request(setup):
    client, value, _ = setup
    job_id = new_job(value)
    with ThreadPoolExecutor(max_workers=2) as pool:
        acquisition = pool.submit(queue.claim, "owner", job_id)
        cancellation = pool.submit(stop, client, job_id)
        claimed, response = acquisition.result(), cancellation.result()
    assert response.status_code == 200
    if claimed:
        with pytest.raises(queue.JobCancelled):
            queue.checkpoint(job_id, "owner")
    with transaction() as db:
        assert db.get(GenerationJob, job_id).status == "cancelled"
    assert queue.claim("next", job_id) is None


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires real PostgreSQL row locks")
def test_postgres_delete_and_claim_never_remove_an_active_product(setup):
    client, value, _ = setup
    product = create(client)
    job_id = new_job(value, product["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        acquisition = pool.submit(queue.claim, "owner", job_id)
        deletion = pool.submit(remove, client, product)
        claimed, response = acquisition.result(), deletion.result()
    if claimed:
        assert response.status_code == 409
        assert client.get(f"/api/platform/products/{product['id']}").status_code == 200
    else:
        assert response.status_code == 200
        with transaction() as db:
            assert db.get(Product, product["id"]).status == "deleted"
            assert db.get(GenerationJob, job_id).status == "cancelled"
