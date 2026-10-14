"""Exercise production image defaults after deleting the seven dashboard overrides."""
import os
from pathlib import Path
import shlex
from unittest.mock import Mock

import pytest
import yaml
from sqlalchemy import select

from catalog_platform import initialize, queue, redis_broker, studio_jobs, worker_wakeup
from catalog_platform.database import transaction
from catalog_platform.models import GenerationJob, WorkerHeartbeat
from test_catalog_platform import setup, create, reference, fake_provider, uid, ORIGIN
from test_stabilization import redis_mode, consume

ROOT = Path(__file__).parent
REMOVED = (
    "GENERATION_QUEUE_BACKEND", "INITIALIZE_EMPTY_DATABASE", "MAX_IMAGES_PER_BATCH",
    "STUDIO_IMAGE_JOBS", "SUITE_SERVICE_ROLE", "WC_WRITE_ENABLED", "WP_MEDIA_WRITE_ENABLED",
)


def image_environment(name):
    defaults = {}
    for line in (ROOT / name).read_text(encoding="utf8").splitlines():
        if line.startswith("ENV "):
            for entry in shlex.split(line[4:]):
                key, value = entry.split("=", 1)
                defaults[key] = value
    return defaults


def without_dashboard_overrides(monkeypatch, dockerfile):
    for key in REMOVED:
        monkeypatch.delenv(key, raising=False)
    for key, value in image_environment(dockerfile).items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("dockerfile", ["Dockerfile.api", "Dockerfile.worker"])
def test_removed_dashboard_overrides_keep_capture_transport_and_existing_schema(monkeypatch, dockerfile):
    without_dashboard_overrides(monkeypatch, dockerfile)
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    assert studio_jobs.enabled()
    assert worker_wakeup.configured()
    engine = Mock(side_effect=AssertionError("Existing database must not be initialized"))
    monkeypatch.setattr(initialize, "engine_for", engine)
    assert not initialize.initialize_empty_database()
    engine.assert_not_called()


def test_removed_overrides_keep_rq_and_dormant_worker_enqueue(redis_mode, monkeypatch):
    client, value, _ = redis_mode
    without_dashboard_overrides(monkeypatch, "Dockerfile.api")
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    with transaction() as db:
        for beat in db.scalars(select(WorkerHeartbeat)):
            beat.updated = 0
    product = create(client)
    reference(client, product)
    provider, _ = fake_provider(monkeypatch)
    data = {"product_ids": [product["id"]], "slots": ["1_hd"]}
    quote = client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).json()
    data.update(confirm=True, request_key=uid(), estimate_token=quote["estimate_token"])
    accepted = client.post("/api/platform/generation/jobs", json=data, headers=ORIGIN)
    assert accepted.status_code == 202, accepted.text
    assert redis_broker.rq_queue().count == 1
    assert provider.call_count == 0
    consume()
    assert provider.call_count == 1
    with transaction() as db:
        assert db.get(GenerationJob, accepted.json()["jobs"][0]["id"]).status == "completed"


def test_removed_override_preserves_thirty_image_limit(setup, monkeypatch):
    client, _, _ = setup
    without_dashboard_overrides(monkeypatch, "Dockerfile.api")
    products = [create(client, sku=f"LIMIT-{index}") for index in range(11)]
    result = client.post("/api/platform/generation/estimate", json={
        "product_ids": [product["id"] for product in products],
        "slots": ["1_hd", "2_uso", "3_comercial"], "quantity": 1,
    }, headers=ORIGIN)
    assert result.status_code == 422, result.text
    assert "límite de imágenes" in result.json()["detail"]


def test_blueprint_does_not_recreate_removed_image_overrides():
    blueprint = yaml.safe_load((ROOT / "deploy/render-platform.yaml").read_text(encoding="utf8"))
    for service in blueprint["services"]:
        keys = {item["key"] for item in service.get("envVars", [])}
        assert not keys.intersection(REMOVED)
        if service["name"] in {"rincon-catalog-api", "rincon-catalog-worker"}:
            assert {"DATABASE_URL", "REDIS_URL", "CREDENTIAL_ENCRYPTION_KEY"} <= keys
