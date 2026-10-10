"""Free Render cold starts and empty-schema safety; no live provider or spend."""

from concurrent.futures import ThreadPoolExecutor
import base64
import os
import subprocess
import sys
import threading
from unittest.mock import Mock
import pytest
import requests
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from catalog_platform import queue, redis_broker, worker_wakeup, worker_web
from catalog_platform.database import engine_for, transaction
from catalog_platform.initialize import initialize_empty_database
from catalog_platform.models import Base, GenerationJob, WorkerHeartbeat, uid
from test_catalog_platform import setup, create, reference, fake_provider, ORIGIN
from test_stabilization import redis_mode, consume


def test_render_generated_standard_base64_key_is_valid_fernet(monkeypatch):
    from catalog_platform.security import seal, unseal
    key = base64.b64encode(bytes([251, 255]) * 16).decode()
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", key)
    assert unseal(seal({"provider": "test"})) == {"provider": "test"}


def test_render_frontend_callback_is_derived_without_changing_explicit_callback(monkeypatch):
    from catalog_platform.render_config import configure_redirect
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.setenv("GOOGLE_REDIRECT_BASE", "https://rincon-frontend.onrender.com/")
    configure_redirect()
    assert os.environ["GOOGLE_REDIRECT_URI"] == "https://rincon-frontend.onrender.com/auth/callback"
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://previous.example/auth/callback")
    configure_redirect()
    assert os.environ["GOOGLE_REDIRECT_URI"] == "https://previous.example/auth/callback"


def test_render_callback_never_uses_untrusted_origin(monkeypatch):
    from catalog_platform.render_config import configure_redirect
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.setenv("GOOGLE_REDIRECT_BASE", "https://rincon.onrender.com@evil.example")
    with pytest.raises(RuntimeError, match="origen HTTPS"):
        configure_redirect()
    assert not os.getenv("GOOGLE_REDIRECT_URI")


def test_worker_http_has_health_only_and_no_sensitive_values(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "secret-key-do-not-expose")
    monkeypatch.setenv("DATABASE_URL", "secret-db-url-do-not-expose")
    ready = threading.Event()
    server = worker_web.health_server(ready, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with requests.get(origin + "/service-health", timeout=3) as response:
            assert response.status_code == 503
        ready.set()
        with requests.get(origin + "/service-health", timeout=3) as response:
            assert response.status_code == 200
            assert response.json()["role"] == "image-worker"
            assert "secret" not in response.text
            assert response.headers["Cache-Control"] == "no-store"
        assert requests.get(origin + "/api/generate", timeout=3).status_code == 404
        assert requests.post(origin + "/service-health", json={"job_id": "arbitrary"}, timeout=3).status_code == 501
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_health_module_never_loads_the_image_runtime():
    code = "import sys; import catalog_platform.worker_web; assert 'studio_api' not in sys.modules; assert 'creative_pipeline' not in sys.modules; assert 'PIL' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


@pytest.mark.parametrize("origin", [
    "http://rincon-worker.onrender.com", "https://evil.example", "https://onrender.com",
    "https://rincon.onrender.com@evil.example", "https://user:password@rincon.onrender.com",
    "https://rincon.onrender.com:443", "https://rincon.onrender.com/path",
    "https://rincon.onrender.com?secret=yes", "https://rincon.onrender.com#fragment",
    "https://rincon.onrender.com\nevil.example",
])
def test_worker_wakeup_rejects_untrusted_origins(monkeypatch, origin):
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", origin)
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    assert not worker_wakeup.configured()


def test_worker_wakeup_does_not_send_secrets_or_follow_redirects(monkeypatch):
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com/")
    response = Mock(status_code=302)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    get = Mock(return_value=response)
    monkeypatch.setattr(worker_wakeup.requests, "get", get)
    worker_wakeup._wake()
    get.assert_called_once_with("https://rincon-worker.onrender.com/service-health", timeout=(5, 90), allow_redirects=False)


def test_worker_wakeup_is_async_and_coalesces_cold_starts(monkeypatch):
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    monkeypatch.setattr(worker_wakeup, "_pending", False)
    monkeypatch.setattr(worker_wakeup, "_last_attempt", -60)
    thread = Mock()
    factory = Mock(return_value=thread)
    monkeypatch.setattr(worker_wakeup.threading, "Thread", factory)
    assert worker_wakeup.notify()
    assert not worker_wakeup.notify()
    thread.start.assert_called_once()
    assert factory.call_args.kwargs["daemon"] is True


def test_failed_wakeup_is_safe_and_can_be_retried(monkeypatch, caplog):
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    monkeypatch.setattr(worker_wakeup.requests, "get", Mock(side_effect=requests.Timeout("secret-response")))
    monkeypatch.setattr(worker_wakeup, "_pending", True)
    worker_wakeup._wake()
    assert not worker_wakeup._pending
    assert "permanece en SQL" in caplog.text and "secret-response" not in caplog.text


def test_thread_start_failure_does_not_fail_an_accepted_sql_job(monkeypatch):
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    monkeypatch.setattr(worker_wakeup, "_pending", False)
    monkeypatch.setattr(worker_wakeup, "_last_attempt", -60)
    thread = Mock()
    thread.start.side_effect = RuntimeError("thread limit")
    monkeypatch.setattr(worker_wakeup.threading, "Thread", Mock(return_value=thread))
    assert not worker_wakeup.notify()
    assert not worker_wakeup._pending


def test_rollback_never_wakes_worker_but_committed_job_does(setup, monkeypatch):
    _, value, _ = setup
    notify = Mock()
    monkeypatch.setattr(worker_wakeup, "notify", notify)
    with pytest.raises(ValueError):
        with transaction() as db:
            job = GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"], request_key=uid(), payload={})
            db.add(job); queue.dispatch(db, job)
            raise ValueError("rollback")
    notify.assert_not_called()
    with transaction() as db:
        job = GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"], request_key=uid(), payload={})
        db.add(job); queue.dispatch(db, job); job_id = job.id
    notify.assert_called_once()
    with transaction() as db:
        assert db.get(GenerationJob, job_id).status == "queued"


def test_dormant_worker_accepts_exactly_one_job_then_consumes_once(redis_mode, monkeypatch):
    client, value, _ = redis_mode
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    notify = Mock()
    monkeypatch.setattr(worker_wakeup, "notify", notify)
    with transaction() as db:
        for beat in db.scalars(select(WorkerHeartbeat)):
            beat.updated = 0
    status = client.get("/api/platform/status").json()
    assert status["ready"] and status["worker_can_queue"] and not status["worker_ready"]
    notify.assert_not_called()  # A read of an idle catalog is not a keepalive.
    product = create(client); reference(client, product)
    maker, _ = fake_provider(monkeypatch)
    data = {"product_ids": [product["id"]], "slots": ["1_hd"]}
    quote = client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).json()
    data.update(confirm=True, request_key=uid(), estimate_token=quote["estimate_token"])
    first = client.post("/api/platform/generation/jobs", json=data, headers=ORIGIN)
    assert first.status_code == 202, first.text
    job_id = first.json()["jobs"][0]["id"]
    replay = client.post("/api/platform/generation/jobs", json=data, headers=ORIGIN)
    assert replay.json()["jobs"][0]["id"] == job_id
    assert maker.call_count == 0 and notify.called
    assert redis_broker.rq_queue().count == 1
    consume()
    assert maker.call_count == 1
    consume()
    assert maker.call_count == 1


def test_unavailable_redis_and_worker_preserve_accepted_sql_job(setup, monkeypatch):
    client, value, _ = setup
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    monkeypatch.setattr(redis_broker, "reachable", lambda: False)
    monkeypatch.setattr(redis_broker, "publish_one", Mock(side_effect=RedisConnectionError()))
    notify = Mock()
    monkeypatch.setattr(worker_wakeup, "notify", notify)
    product = create(client); reference(client, product)
    data = {"product_ids": [product["id"]], "slots": ["1_hd"]}
    quote = client.post("/api/platform/generation/estimate", json=data, headers=ORIGIN).json()
    data.update(confirm=True, request_key=uid(), estimate_token=quote["estimate_token"])
    result = client.post("/api/platform/generation/jobs", json=data, headers=ORIGIN)
    assert result.status_code == 202, result.text
    with transaction() as db:
        assert db.get(GenerationJob, result.json()["jobs"][0]["id"]).status == "queued"
    client.get("/api/platform/status")
    assert notify.call_count == 2  # Actual queued work permits a wake retry.
    client.cookies.clear(); notify.reset_mock()
    client.get("/api/platform/status")
    notify.assert_not_called()


@pytest.fixture
def empty_database(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("INITIALIZE_EMPTY_DATABASE", "true")
    postgres_url = os.getenv("TEST_DATABASE_URL")
    if not postgres_url:
        url = "sqlite:///" + str(tmp_path / "empty.db")
        monkeypatch.setenv("DATABASE_URL", url)
        yield engine_for(url)
        return
    # Only create/drop our own disposable schema, never existing test tables.
    schema = "rincon_empty_test_" + uid().replace("-", "")
    original = engine_for(postgres_url)
    with original.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(postgres_url).update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", url)
    engine = engine_for(url)
    try:
        yield engine
    finally:
        engine.dispose()
        with original.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_empty_database_opt_in_and_idempotent_schema(empty_database, monkeypatch):
    monkeypatch.delenv("INITIALIZE_EMPTY_DATABASE")
    assert not initialize_empty_database()
    assert inspect(empty_database).get_table_names() == []
    monkeypatch.setenv("INITIALIZE_EMPTY_DATABASE", "true")
    assert initialize_empty_database()
    assert set(inspect(empty_database).get_table_names()) == set(Base.metadata.tables)
    assert not initialize_empty_database()


def test_existing_foreign_database_is_rejected_without_ddl(empty_database):
    with empty_database.begin() as connection:
        connection.execute(text("CREATE TABLE existing_inventory (sku VARCHAR(40))"))
        connection.execute(text("INSERT INTO existing_inventory VALUES ('KEEP-ME')"))
    with pytest.raises(RuntimeError, match="no está vacía"):
        initialize_empty_database()
    assert inspect(empty_database).get_table_names() == ["existing_inventory"]
    with empty_database.connect() as connection:
        assert connection.execute(text("SELECT sku FROM existing_inventory")).scalar() == "KEEP-ME"


def test_existing_incomplete_platform_schema_is_not_changed(empty_database):
    assert initialize_empty_database()
    with empty_database.begin() as connection:
        connection.execute(text("ALTER TABLE rincon_generation_jobs DROP COLUMN message"))
    with pytest.raises(RuntimeError, match="está incompleto"):
        initialize_empty_database()
    assert "message" not in {column["name"] for column in inspect(empty_database).get_columns("rincon_generation_jobs")}


def test_concurrent_postgres_empty_initialization_is_serialized(empty_database):
    if empty_database.dialect.name != "postgresql":
        pytest.skip("Concurrent DDL is verified on the dedicated CI PostgreSQL service")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: initialize_empty_database(), [1, 2]))
    assert sorted(results) == [False, True]
    assert set(inspect(empty_database).get_table_names()) == set(Base.metadata.tables)
