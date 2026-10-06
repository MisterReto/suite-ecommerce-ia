"""Regression across HTTP, Redis/RQ, SQL, the accepted image pipeline and Drive.

TEST_REDIS_URL must point to a dedicated test Redis. No live provider is called.
"""
import io
import json
import os
from pathlib import Path
from unittest.mock import Mock
import pytest
from PIL import Image
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import SimpleWorker, Worker
from rq.serializers import JSONSerializer
from sqlalchemy import select, func
from test_catalog_platform import setup, create, reference, enqueue, execute, fake_provider, ORIGIN
from catalog_platform import queue, worker, redis_broker
from catalog_platform.database import transaction
from catalog_platform.models import GenerationJob, GenerationBatch, WebhookEvent, uid
from catalog_platform.security import seal


@pytest.fixture
def redis_mode(setup, monkeypatch):
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL enables the real Redis/RQ regressions")
    monkeypatch.setenv("REDIS_URL", url)
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    monkeypatch.setattr(redis_broker, "QUEUE_NAME", "rincon-test-" + uid())
    assert redis_broker.reachable()
    queue.heartbeat("test_" + setup[1]["platform_tenant"])
    yield setup
    redis_broker.rq_queue().delete(delete_jobs=True)


def consume(fork=False):
    q = redis_broker.rq_queue()
    kind = Worker if fork else SimpleWorker
    kind([q], connection=q.connection, serializer=JSONSerializer).work(burst=True, logging_level="WARNING")


def test_rq_delivery_contains_only_id_and_executes_once(redis_mode, monkeypatch):
    client, value, drive = redis_mode
    p = create(client); reference(client, p)
    maker, _ = fake_provider(monkeypatch)
    job, _ = enqueue(client, value, p)
    assert maker.call_count == 0  # HTTP never called the paid image function.
    q = redis_broker.rq_queue()
    delivered = q.jobs[0]
    assert list(delivered.args) == [job["id"]] and delivered.kwargs == {}
    assert all(secret not in delivered.data.decode() for secret in ["private-token", "private-refresh", "test-key-no-spend"])
    redis_broker.publish_committed([job["id"], job["id"]])
    assert len(q.job_ids) == 1
    consume()
    assert maker.call_count == 3
    worker.execute_job(job["id"])
    assert maker.call_count == 3
    assets = client.get("/api/platform/assets").json()["items"]
    assert len(assets) == 3 and all(a["product_id"] == p["id"] for a in assets)
    generated = [u for u in drive.uploads if u["properties"] and u["properties"].get("slot")]
    assert {u["name"] for u in generated} == {p["sku"] + "_1_hd.jpg", p["sku"] + "_2_uso.jpg", p["sku"] + "_3_comercial.jpg"}
    assert all("imagenes_temporales/" + job["id"] == u["folder"] for u in generated)


def test_redis_outage_after_commit_is_reconciled_without_losing_job(redis_mode, monkeypatch):
    client, value, _ = redis_mode
    p = create(client); reference(client, p)
    publish = redis_broker.publish_one
    monkeypatch.setattr(redis_broker, "publish_one", Mock(side_effect=RedisConnectionError()))
    job, _ = enqueue(client, value, p, slots=["1_hd"])
    assert redis_broker.rq_queue().count == 0
    with transaction() as db:
        assert db.get(GenerationJob, job["id"]).status == "queued"
    monkeypatch.setattr(redis_broker, "publish_one", publish)
    redis_broker.reconcile(); redis_broker.reconcile()
    assert redis_broker.rq_queue().job_ids == ["rincon-" + job["id"]]


def test_rolled_back_sql_job_never_reaches_redis(redis_mode):
    _, value, _ = redis_mode
    key = uid()
    with pytest.raises(ValueError):
        with transaction() as db:
            job = GenerationJob(id=key, tenant_id=value["platform_tenant"], actor=value["email"], request_key=uid(), payload={})
            db.add(job); queue.dispatch(db, job)
            raise ValueError("rollback")
    assert redis_broker.rq_queue().count == 0
    with transaction() as db: assert db.get(GenerationJob, key) is None


def test_batch_is_one_job_per_product_and_has_limits(setup, monkeypatch):
    client, value, _ = setup
    first, second = create(client), create(client, sku="TEST-INTEGRATION-SECOND")
    reference(client, first); reference(client, second)
    queue.heartbeat("test_" + value["platform_tenant"])
    data = {"product_ids": [first["id"], second["id"]], "slots": ["1_hd"]}
    quote = client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).json()
    result = client.post("/api/platform/generation/jobs", json={**data, "confirm": True, "request_key": uid(), "estimate_token": quote["estimate_token"]}, headers=ORIGIN)
    assert result.status_code == 202 and len(result.json()["jobs"]) == 2
    assert all(j["batch_id"] == result.json()["batch_id"] for j in result.json()["jobs"])
    with transaction() as db:
        batch = db.get(GenerationBatch, result.json()["batch_id"])
        assert batch.product_count == batch.image_count == 2
    monkeypatch.setenv("MAX_IMAGES_PER_BATCH", "1")
    assert client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).status_code == 422
    monkeypatch.setenv("MAX_IMAGES_PER_BATCH", "10")
    monkeypatch.setenv("MAX_ESTIMATED_BATCH_COST", "0")
    assert client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).status_code == 422
    with transaction() as db:
        failed = db.get(GenerationJob, result.json()["jobs"][0]["id"])
        failed.status = "failed"
        job_id = failed.id
    retry = client.post(f"/api/platform/jobs/{job_id}/retry", json={"confirm": True, "request_key": uid()}, headers=ORIGIN)
    assert retry.status_code == 422  # A retry cannot bypass the current USD cap.


def test_request_key_cannot_be_reused_for_another_product(setup):
    client, value, _ = setup
    first, second = create(client), create(client, sku="TEST-INTEGRATION-OTHER")
    reference(client, first); reference(client, second)
    key = uid(); enqueue(client, value, first, slots=["1_hd"], key=key)
    data = {"product_ids": [second["id"]], "slots": ["1_hd"]}
    quote = client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).json()
    result = client.post("/api/platform/generation/jobs", json={**data, "confirm": True, "request_key": key, "estimate_token": quote["estimate_token"]}, headers=ORIGIN)
    assert result.status_code == 409
    with transaction() as db:
        assert len(list(db.scalars(select(GenerationJob).where(GenerationJob.tenant_id == value["platform_tenant"])))) == 1


def test_paid_endpoints_have_configurable_session_rate_limit(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setenv("GENERATION_REQUESTS_PER_MINUTE", "1")
    # Invalid data also cannot be flooded indefinitely under a valid session.
    assert client.post("/api/generate", json={"slots": []}, headers=ORIGIN).status_code == 422
    result = client.post("/api/generate", json={"slots": []}, headers=ORIGIN)
    assert result.status_code == 429 and result.headers["retry-after"] == "60"


def capture(client):
    image = Image.new("RGB", (120, 180), "orange"); buf = io.BytesIO(); image.save(buf, "PNG")
    up = client.post("/api/uploads", files={"image": ("front.png", buf.getvalue(), "image/png")}, headers=ORIGIN).json()
    assert client.post("/api/capture", json={"front_id": up["id"]}, headers=ORIGIN).status_code == 200
    assert client.put("/api/draft", json={"sku": "TEST-INTEGRATION-CAPTURE", "name": "Pocky", "brand": "Glico"}, headers=ORIGIN).status_code == 200


def test_capture_worker_correction_and_recovery_use_original_pipeline(redis_mode, monkeypatch):
    client, value, drive = redis_mode
    monkeypatch.setenv("STUDIO_IMAGE_JOBS", "worker")
    maker, planner = fake_provider(monkeypatch)
    capture(client)
    request = {"slots": ["1_hd", "2_uso", "3_comercial"], "request_key": uid(), "confirm_cost": True}
    monkeypatch.setattr("studio_api.start_job", Mock(side_effect=AssertionError("Generation used the API executor")))
    first = client.post("/api/generate", json=request, headers=ORIGIN)
    assert first.status_code == 202, first.text
    replay = client.post("/api/generate", json=request, headers=ORIGIN)
    assert replay.json()["job"]["id"] == first.json()["job"]["id"]
    assert maker.call_count == 0
    consume()
    result = client.get("/api/jobs/" + first.json()["job"]["id"]).json()
    assert result["job"]["status"] == "completed" and len(result["draft"]["images"]) == 3
    assert maker.call_count == 3 and planner.call_count == 1
    # Simulate a fresh API session after login: files are recovered by Drive IDs.
    import studio_api as studio
    studio.runtime._eliminar_sesion(value["session_id"])
    fresh = {**value, "studio_files": {}, "file_namespace": "TESTINTEGRATION" + uid().replace("-", "")}
    fresh.pop("studio_draft", None); fresh.pop("studio_loaded_results", None)
    studio.runtime.SESSIONS[fresh["session_id"]] = fresh
    recovered = client.get("/api/jobs/" + first.json()["job"]["id"])
    assert recovered.status_code == 200
    image_id = recovered.json()["draft"]["images"]["2_uso"]["id"]
    with Image.open(io.BytesIO(client.get("/api/files/" + image_id).content)) as image:
        assert image.format == "JPEG" and image.size == (1024, 1024)
    correction = client.post("/api/images/2_uso/correct", json={"feedback": "Cambiar la mano derecha", "request_key": uid(), "confirm_cost": True}, headers=ORIGIN)
    assert correction.status_code == 202, correction.text
    consume()
    corrected = client.get("/api/jobs/" + correction.json()["job"]["id"]).json()
    assert corrected["draft"]["images"]["2_uso"]["history"] == ["Cambiar la mano derecha"]
    assert maker.call_count == 4 and planner.call_count == 1
    assert maker.call_args.kwargs["previous"] and len(maker.call_args.args[1]) == 1
    approval = client.post("/api/images/2_uso/approve", json={"approved": True}, headers=ORIGIN)
    assert approval.status_code == 200
    from catalog_platform.studio_jobs import record_saved
    current = fresh["studio_draft"]
    current["saved"] = "💾 TEST-INTEGRATION guardado"
    record_saved(fresh, current)
    fresh.pop("studio_draft"); fresh.pop("studio_loaded_results", None)
    restored = client.get("/api/session").json()["draft"]
    assert restored["images"]["2_uso"]["approved"]
    assert restored["saved"] == "💾 TEST-INTEGRATION guardado"


def test_forked_rq_worker_completes_signed_sql_event(redis_mode):
    client, value, _ = redis_mode
    with transaction() as db:
        event = WebhookEvent(tenant_id=value["platform_tenant"], provider="woocommerce", event_id=uid(), event_type="test", payload_hash=uid(), encrypted_payload=seal({}))
        db.add(event); db.flush()
        job = GenerationJob(tenant_id=value["platform_tenant"], actor="webhook", kind="webhook", request_key=uid(), payload={"event_id": event.id})
        db.add(job); queue.dispatch(db, job); job_id = job.id
    consume(fork=True)
    with transaction() as db: assert db.get(GenerationJob, job_id).status == "completed"
    # A fork must not corrupt the parent's psycopg prepared-statement state.
    assert create(client, sku="TEST-INTEGRATION-AFTER-FORK")["stock"] == 10


def test_regenerate_keeps_old_asset_and_removes_previous_edit_reference(setup, monkeypatch):
    client, value, drive = setup
    p = create(client); reference(client, p); maker, _ = fake_provider(monkeypatch)
    job, _ = enqueue(client, value, p, slots=["1_hd"]); execute(job, value, drive)
    asset = client.get("/api/platform/assets").json()["items"][0]
    result = client.post(f"/api/platform/assets/{asset['id']}/regenerate", json={"request_key": uid(), "confirm_cost": True}, headers=ORIGIN)
    assert result.status_code == 202
    execute(result.json()["job"], value, drive)
    assert maker.call_count == 2 and maker.call_args.kwargs["previous"] is None
    assert len(client.get("/api/platform/assets").json()["items"]) == 2


def test_allowlist_is_required_in_separate_mode_and_secrets_are_redacted(monkeypatch):
    from oauth_guard import email_allowed
    from app_security import public_error
    monkeypatch.setenv("APP_ALLOWED_EMAILS", "")
    monkeypatch.setenv("APP_REQUIRE_ALLOWLIST", "true")
    monkeypatch.setenv("APP_ROLE_MAP", "{}")
    assert not email_allowed("unknown@example.test")
    monkeypatch.setenv("APP_ROLE_MAP", '{"Owner@Example.test":"admin"}')
    assert email_allowed("owner@example.test")
    monkeypatch.setenv("REDIS_URL", "redis://private:private-password@example.test:6379")
    assert "private-password" not in public_error(RuntimeError(os.environ["REDIS_URL"]))


def test_unconfigured_provider_cannot_silently_charge_gemini(monkeypatch):
    from image_generation_service import ImageGenerationService
    monkeypatch.setenv("AI_PROVIDER", "flux")
    with pytest.raises(RuntimeError): ImageGenerationService()
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    assert ImageGenerationService().provider.name == "gemini"


def test_worker_usage_is_recorded_outside_api_memory(setup, monkeypatch):
    client, value, _ = setup
    monkeypatch.setenv("STUDIO_IMAGE_JOBS", "worker")
    p = create(client); reference(client, p); fake_provider(monkeypatch)
    job, _ = enqueue(client, value, p, slots=["1_hd"])
    monkeypatch.setattr("gemini_gateway.usage_for_key", Mock(side_effect=[
        {"count": 2, "input_tokens": 100, "output_tokens": 10},
        {"count": 3, "input_tokens": 120, "output_tokens": 15},
    ]))
    claimed = queue.claim(worker.OWNER)
    assert worker.process(claimed)
    queue.finish(job["id"], worker.OWNER, True, "Completado")
    with transaction() as db:
        assert db.get(GenerationJob, job["id"]).payload["usage"] == {"count": 1, "input_tokens": 20, "output_tokens": 5}
    from catalog_platform.studio_jobs import recorded_usage
    assert recorded_usage(value)["count"] == 1


def test_sheets_write_is_one_cell_and_duplicates_or_stale_values_block_it():
    from sheets_service import SheetsService
    values = Mock(); client = Mock(); client.spreadsheets.return_value.values.return_value = values
    client.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Lista completa", "gridProperties": {"rowCount": 1000}}}]
    }
    replies = {
        "'Lista completa'!A1:AZ1": {"values": [["sku", "", "Existencias"]]},
        "'Lista completa'!A2:A501": {"values": [["TEST-INTEGRATION-ONE"]]},
        "'Lista completa'!C2": {"values": [[7]]},
        "'Lista completa'!A2": {"values": [["TEST-INTEGRATION-ONE"]]},
    }
    values.get.side_effect = lambda **args: Mock(execute=lambda: replies.get(args["range"], {"values": []}))
    def update(**args):
        replies[args["range"]] = args["body"]
        return Mock(execute=lambda: {})
    values.update.side_effect = update
    service = SheetsService(client, "test-sheet")
    assert service.update_cell("TEST-INTEGRATION-ONE", "Existencias", 8, expected=7)["range"] == "'Lista completa'!C2"
    assert values.update.call_args.kwargs["body"] == {"values": [[8]]}
    with pytest.raises(ValueError): service.update_cell("TEST-INTEGRATION-ONE", "Existencias", 9, expected=7)
    replies["'Lista completa'!A2:A501"] = {"values": [["TEST-INTEGRATION-ONE"], ["TEST-INTEGRATION-ONE"]]}
    with pytest.raises(ValueError): service.update_cell("TEST-INTEGRATION-ONE", "Existencias", 9)
    assert values.update.call_count == 1
    # A gap of blank rows must not hide a later duplicate.
    replies["'Lista completa'!A2:A501"] = {"values": [["TEST-INTEGRATION-ONE"]]}
    replies["'Lista completa'!A502:A1000"] = {"values": [["TEST-INTEGRATION-ONE"]]}
    with pytest.raises(ValueError): service.update_cell("TEST-INTEGRATION-ONE", "Existencias", 9)
    assert values.update.call_count == 1


def test_drive_save_preserves_old_file_before_replacement_and_is_idempotent(tmp_path, monkeypatch):
    from drive_service import DriveService
    client = Mock(); files = client.files.return_value
    service = DriveService(client, "root")
    monkeypatch.setattr(service, "owns", lambda _: True)
    old = {"id": "existing-file", "name": "TEST-INTEGRATION-ONE_1_hd.jpg"}
    monkeypatch.setattr(service, "find", lambda name, folder: [old] if folder == "generated" else [])
    metadata = {"appProperties": {}}
    monkeypatch.setattr(service, "metadata", lambda _: metadata)
    monkeypatch.setattr(service, "working_folder", lambda *args: "backup-folder")
    sequence = []
    files.copy.return_value.execute.side_effect = lambda: sequence.append("backup") or {"id": "backup"}
    files.update.return_value.execute.side_effect = lambda: sequence.append("update") or old
    path = tmp_path / "candidate.jpg"; Image.new("RGB", (1024, 1024)).save(path, "JPEG")
    assert service.save_approved(path, old["name"], "generated", "approved-asset") == old
    assert sequence == ["backup", "update"]
    assert files.copy.call_args.kwargs["fileId"] == old["id"]
    metadata["appProperties"]["asset_id"] = "approved-asset"
    service.save_approved(path, old["name"], "generated", "approved-asset")
    assert sequence == ["backup", "update"]
    metadata["appProperties"] = {}
    files.copy.return_value.execute.side_effect = RuntimeError("backup failed")
    with pytest.raises(RuntimeError): service.save_approved(path, old["name"], "generated", "other-asset")
    assert files.update.call_count == 1
    monkeypatch.setattr(service, "find", lambda *_: [old, old])
    with pytest.raises(ValueError): service.save_approved(path, old["name"], "generated", "other-asset")


def test_drive_download_removes_partial_file_and_rejects_other_paths(monkeypatch):
    from drive_service import DriveService
    service = DriveService(Mock(), "root")
    monkeypatch.setattr(service, "owns", lambda _: True)
    def broken_download(key, stream):
        stream.write(b"partial")
        raise ValueError("invalid image")
    monkeypatch.setattr(service, "_download", broken_download)
    path = Path("/tmp/TESTINTEGRATION" + uid().replace("-", "") + ".jpg")
    with pytest.raises(ValueError): service.download_to("file", path)
    assert not path.exists()
    with pytest.raises(ValueError): service.download_to("file", "/var/tmp/not-allowed.jpg")


def test_capture_save_uses_backup_boundary_only_when_separated(tmp_path, monkeypatch):
    import app
    from drive_service import DriveService
    service = DriveService(Mock(), "root")
    path = tmp_path / "TEST-INTEGRATION.jpg"
    Image.new("RGB", (1024, 1024)).save(path, "JPEG")
    saver = Mock(return_value={"id": "same-canonical-id"})
    monkeypatch.setattr(service, "save_approved", saver)
    monkeypatch.setenv("STUDIO_IMAGE_JOBS", "worker")
    assert app._subir_imagen_drive(service, "generated", path.name, path) == "same-canonical-id"
    assert saver.call_args.args[3].startswith("capture-")
    monkeypatch.setenv("STUDIO_IMAGE_JOBS", "local")
    monkeypatch.setattr(app, "_buscar_archivo", lambda *_: "same-canonical-id")
    app._subir_imagen_drive(service, "generated", path.name, path)
    assert saver.call_count == 1
    service.files().update.assert_called_once()


def test_worker_restart_does_not_repeat_uncertain_paid_call(redis_mode, monkeypatch):
    client, value, _ = redis_mode
    p = create(client); reference(client, p)
    maker, _ = fake_provider(monkeypatch)
    job, _ = enqueue(client, value, p, slots=["1_hd"])
    with transaction() as db:
        stored = db.get(GenerationJob, job["id"])
        stored.status = "processing"; stored.lease_owner = "lost-worker"; stored.lease_until = 0
        stored.payload = {**stored.payload, "in_flight": {"operation": "image_generation"}}
    redis_broker.reconcile(); consume()
    assert maker.call_count == 0
    with transaction() as db:
        stored = db.get(GenerationJob, job["id"])
        assert stored.status == "failed" and "incierto" in stored.message
