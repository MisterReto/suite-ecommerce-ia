"""Controlled individual publication through FastAPI, durable SQL jobs and the real worker."""
from copy import deepcopy
from unittest.mock import Mock
import pytest
from sqlalchemy import select

from catalog_platform import queue, worker, redis_broker, worker_wakeup
from catalog_platform.database import transaction
from catalog_platform.models import GenerationJob, uid
from catalog_platform.woocommerce_export import Exporter
from test_catalog_platform import setup, ORIGIN
from test_woocommerce_colab import store, source


@pytest.fixture
def publication(setup, store, monkeypatch):
    client, value, _ = setup
    def load(engine, value, include_images=True):
        engine.ns.update(deepcopy(source()))
        return engine
    monkeypatch.setattr(Exporter, "load", load)
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    monkeypatch.setattr(redis_broker, "reachable", lambda: True)
    monkeypatch.setattr(redis_broker, "publish_one", Mock())
    monkeypatch.setattr(worker_wakeup, "notify", Mock())
    from studio_api import runtime
    monkeypatch.setattr(runtime, "_get_drive_service", Mock())
    return client, value, store


def preview(client, kind="simple", sku="S1"):
    response = client.post("/api/woocommerce/preview", json={
        "selection": {"kind": kind, "sku": sku},
        "options": {"images": False, "stock": True, "tags": True},
    }, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, reviewed, request_key=None, confirm=True):
    return client.post("/api/woocommerce/jobs", json={
        "preview_token": reviewed["preview_token"], "request_key": request_key or uid(),
        "confirm": confirm,
    }, headers=ORIGIN)


def test_catalog_search_and_filters_use_sheet_source(publication):
    client, _, _ = publication
    result = client.get("/api/woocommerce/catalog", params={"q": "V1", "kind": "variant"})
    assert result.status_code == 200, result.text
    assert [item["sku"] for item in result.json()["rows"]] == ["V1"]
    assert result.json()["brands"] == ["Marca original"]


def test_individual_is_reviewed_and_durable_before_worker_writes(publication, monkeypatch):
    client, value, (calls, products, *_) = publication
    reviewed = preview(client)
    assert not calls
    assert submit(client, reviewed, confirm=False).status_code == 422
    key = uid()
    accepted = submit(client, reviewed, key)
    assert accepted.status_code == 202, accepted.text
    job_id = accepted.json()["job"]["id"]
    assert not products
    assert submit(client, reviewed, key).json()["job"]["id"] == job_id
    with transaction() as db:
        job = db.get(GenerationJob, job_id)
        assert job.kind == "woocommerce_export" and job.provider == "woocommerce"
        assert "test-read-write-secret" not in str(job.payload)
    maker = Mock(side_effect=AssertionError("Publication must not generate AI images"))
    monkeypatch.setattr(worker, "generation", maker)
    worker.execute_job(job_id)
    result = client.get("/api/woocommerce/jobs/" + job_id).json()["job"]
    assert result["status"] == "completed", result
    assert products["S1"]["status"] == "draft" and products["S1"]["stock_quantity"] == 4
    assert any(event["action"] == "producto_creado" for event in result["events"])
    maker.assert_not_called()


def test_individual_variant_creates_parent_with_all_attributes(publication):
    client, _, (_, products, variations, _) = publication
    accepted = submit(client, preview(client, "variant", "V1"))
    assert accepted.status_code == 202, accepted.text
    worker.execute_job(accepted.json()["job"]["id"])
    assert products["FAMILIA"]["attributes"][0]["options"] == ["Chocolate", "Fresa"]
    assert set(variations) == {"V1"}


def test_permissions_and_cross_actor_jobs(publication):
    client, value, _ = publication
    reviewed = preview(client)
    value["email"] = "viewer@example.test"
    assert submit(client, reviewed).status_code == 403
    value["email"] = "admin@example.test"
    result = submit(client, reviewed)
    value["email"] = "editor@example.test"
    assert client.get("/api/woocommerce/jobs/" + result.json()["job"]["id"]).status_code == 404
    client.cookies.clear()
    assert client.get("/api/woocommerce/catalog").status_code == 401


def test_stale_preview_and_reused_key_cannot_change_selection(publication):
    client, value, _ = publication
    reviewed = preview(client)
    key = uid()
    assert submit(client, reviewed, key).status_code == 202
    different = preview(client, "variant", "V1")
    assert submit(client, different, key).status_code == 409
    value["woocommerce_previews"][different["preview_token"]]["expires"] = 0
    assert submit(client, different).status_code == 422


def test_batch_selection_deduplicates_family_and_queues_independent_jobs(publication):
    client, _, (_, products, variations, _) = publication
    selections = [{"kind": "simple", "sku": "S1"}, {"kind": "family", "sku": "FAMILIA"},
                  {"kind": "variant", "sku": "V1"}, {"kind": "simple", "sku": "S1"}]
    reviewed = client.post("/api/woocommerce/batch-preview", json={"selections": selections,
        "options": {"images": False, "stock": True}}, headers=ORIGIN)
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert len(body["previews"]) == 2 and len(body["omitted"]) == 2 and not body["errors"]
    request = {"preview_token": body["preview_token"], "request_key": uid(), "confirm": True}
    accepted = client.post("/api/woocommerce/batch-jobs", json=request, headers=ORIGIN)
    assert accepted.status_code == 202, accepted.text
    result = accepted.json()
    assert len(result["jobs"]) == 2 and not products
    replay = client.post("/api/woocommerce/batch-jobs", json=request, headers=ORIGIN)
    assert {j["id"] for j in replay.json()["jobs"]} == {j["id"] for j in result["jobs"]}
    for job in result["jobs"]:
        worker.execute_job(job["id"])
    assert set(products) == {"S1", "FAMILIA"} and set(variations) == {"V1", "V2"}
    assert all(job["status"] == "completed" for job in client.get("/api/woocommerce/jobs").json()["jobs"])


def test_preview_errors_never_partially_submit_a_batch(publication):
    client, _, (calls, *_) = publication
    body = client.post("/api/woocommerce/batch-preview", json={"selections": [
        {"kind": "simple", "sku": "S1"}, {"kind": "variant", "sku": "MISSING"}],
        "options": {"images": False}}, headers=ORIGIN).json()
    assert body["errors"]
    accepted = client.post("/api/woocommerce/batch-jobs", json={"preview_token": body["preview_token"],
        "request_key": uid(), "confirm": True}, headers=ORIGIN)
    assert accepted.status_code == 422
    assert client.get("/api/woocommerce/jobs").json()["jobs"] == [] and not calls


def test_failed_batch_insert_rolls_back_every_job(publication, monkeypatch):
    client, _, _ = publication
    body = client.post("/api/woocommerce/batch-preview", json={"selections": [
        {"kind": "simple", "sku": "S1"}, {"kind": "variant", "sku": "V1"}],
        "options": {"images": False}}, headers=ORIGIN).json()
    from catalog_platform import woocommerce_api
    original = woocommerce_api.enqueue
    count = 0
    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("Controlled SQL insert failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(woocommerce_api, "enqueue", fail_second)
    with pytest.raises(RuntimeError, match="Controlled SQL"):
        client.post("/api/woocommerce/batch-jobs", json={"preview_token": body["preview_token"],
            "request_key": uid(), "confirm": True}, headers=ORIGIN)
    assert client.get("/api/woocommerce/jobs").json()["jobs"] == []


def test_retry_uses_existing_products_without_duplicate_writes(publication, monkeypatch):
    client, _, (calls, products, variations, _) = publication
    accepted = submit(client, preview(client, "family", "FAMILIA")).json()["job"]
    original = Exporter.execute
    def fail_after_completed(engine, *args):
        original(engine, *args)
        raise ValueError("Controlled failure after acknowledgment")
    monkeypatch.setattr(Exporter, "execute", fail_after_completed)
    worker.execute_job(accepted["id"])
    assert client.get("/api/woocommerce/jobs/" + accepted["id"]).json()["job"]["status"] == "failed"
    monkeypatch.setattr(Exporter, "execute", original)
    retry = client.post("/api/platform/jobs/" + accepted["id"] + "/retry", json={"confirm": True,
        "request_key": uid()}, headers=ORIGIN)
    assert retry.status_code == 202, retry.text
    worker.execute_job(retry.json()["job"]["id"])
    assert len(products) == 1 and len(variations) == 2
    assert len([call for call in calls if call["method"] == "POST" and call["endpoint"].endswith("/variations")]) == 2


def test_lost_write_response_requires_review_and_reconciles_by_sku(publication, monkeypatch):
    import requests
    client, _, (_, products, *_) = publication
    original = requests.Session.request
    def lose_response(session, method, url, **kwargs):
        response = original(session, method, url, **kwargs)
        if method.upper() == "POST" and url.endswith("/wc/v3/products"):
            raise requests.Timeout("Controlled response loss")
        return response
    monkeypatch.setattr(requests.Session, "request", lose_response)
    accepted = submit(client, preview(client)).json()["job"]
    worker.execute_job(accepted["id"])
    failed = client.get("/api/woocommerce/jobs/" + accepted["id"]).json()["job"]
    assert failed["status"] == "failed" and failed["uncertain"] and set(products) == {"S1"}
    body = {"confirm": True, "request_key": uid()}
    assert client.post("/api/platform/jobs/" + accepted["id"] + "/retry", json=body, headers=ORIGIN).status_code == 422
    monkeypatch.setattr(requests.Session, "request", original)
    body["uncertainty_reviewed"] = True
    retry = client.post("/api/platform/jobs/" + accepted["id"] + "/retry", json=body, headers=ORIGIN)
    assert retry.status_code == 202, retry.text
    worker.execute_job(retry.json()["job"]["id"])
    assert len(products) == 1
