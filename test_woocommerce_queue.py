"""RQ delivery/priority tests use isolated Redis emulation; providers remain controlled."""
import importlib
import os
from unittest.mock import Mock

import fakeredis
from rq import SimpleWorker
from rq.serializers import JSONSerializer
from rq.timeouts import TimerDeathPenalty
from sqlalchemy import select

from catalog_platform import redis_broker, worker
from catalog_platform.database import transaction
from catalog_platform.models import GenerationJob, uid
from test_woocommerce_api import publication, preview, submit
from test_catalog_platform import setup
from test_woocommerce_colab import store

PUBLISH_ONE = redis_broker.publish_one


class ControlledWorker(SimpleWorker):
    death_penalty_class = TimerDeathPenalty


def test_rq_delivers_only_id_and_consumes_publication_once(publication, monkeypatch):
    client, value, (_, products, *_) = publication
    connection = fakeredis.FakeRedis(version=(7, 0))
    monkeypatch.setattr(redis_broker, "connection", lambda: connection)
    monkeypatch.setattr(redis_broker, "QUEUE_NAME", "test-images-" + uid())
    monkeypatch.setattr(redis_broker, "PUBLICATION_QUEUE_NAME", "test-publication-" + uid())
    # Restore the real outbox delivery implementation, replaced by the HTTP-only fixture.
    from catalog_platform import redis_broker as broker
    monkeypatch.setattr(broker, "connection", lambda: connection)
    monkeypatch.setattr(broker, "QUEUE_NAME", "test-images-" + uid())
    monkeypatch.setattr(broker, "PUBLICATION_QUEUE_NAME", "test-publication-" + uid())
    monkeypatch.setattr(broker, "publish_one", PUBLISH_ONE)
    result = submit(client, preview(client))
    assert result.status_code == 202, result.text
    job_id = result.json()["job"]["id"]
    publication_queue = broker.rq_queue("woocommerce_export")
    assert publication_queue.count == 1 and broker.rq_queue().count == 0
    assert list(publication_queue.jobs[0].args) == [job_id]
    assert "test-read-write-secret" not in publication_queue.jobs[0].data.decode()
    ControlledWorker([broker.rq_queue(), publication_queue], connection=connection,
                     serializer=JSONSerializer).work(burst=True, logging_level="WARNING")
    assert set(products) == {"S1"}
    with transaction() as db:
        assert db.get(GenerationJob, job_id).status == "completed"
    worker.execute_job(job_id)
    assert len(products) == 1


def test_worker_queue_order_preserves_image_priority(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://test-only.invalid")
    from catalog_platform import rq_settings
    importlib.reload(rq_settings)
    assert rq_settings.QUEUES == [redis_broker.QUEUE_NAME, redis_broker.PUBLICATION_QUEUE_NAME]
