"""Real API/SQL/RQ boundaries with a controlled Loyverse transport; no live writes."""
import ast
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest
import requests
from PIL import Image
from rq import SimpleWorker
from rq.serializers import JSONSerializer
from sqlalchemy import select

from catalog_platform import loyverse_export as export, queue, worker, redis_broker, worker_wakeup
from catalog_platform.database import transaction
from catalog_platform.models import GenerationJob, IntegrationAccount, uid
from catalog_platform.loyverse_connections import connections, PROVIDER, JOB_PROVIDER
from test_catalog_platform import setup, ORIGIN
from test_woocommerce_queue import ControlledWorker

TOKEN_A = "ly-account-a-private-token"
TOKEN_B = "ly-account-b-private-token"


def source():
    base = {"precio": "35.50", "categorias": "Dulces", "Marca": "Glico",
            "descripcion_corta": "Texto corto", "descripcion_larga": "Texto largo"}
    return {"SIMPLES": {"S1": {**base, "sku": "S1", "nombre_producto": "Pocky", "tipo": "simple"}},
        "PADRES": {"F1": {**base, "sku": "F1", "nombre_producto": "Pocky sabores", "tipo": "variable"}},
        "VARIANTES": {sku: {**base, "sku": sku, "sku_padre": "F1", "nombre_producto": "Pocky " + taste, "tipo": "variation"}
            for sku, taste in (("V1", "Fresa"), ("V2", "Chocolate"))},
        "EXTRA": {"S1": {"codigo_barras": "001234567890"}},
        "CSV_V": {sku: {"Nombre del atributo 1": "Sabor", "Valor(es) del atributo 1": taste}
                  for sku, taste in (("V1", "Fresa"), ("V2", "Chocolate"))}, "IMAGE_FILES": []}


def response(data, status=200):
    result = requests.Response()
    result.status_code, result._content = status, json.dumps(data).encode()
    return result


@pytest.fixture
def loyverse(setup, monkeypatch):
    client, value, drive = setup
    calls = []
    states = {token: {"merchant_id": name, "items": {}, "categories": [], "images": [],
                     "stores": [{"id": name + "-north", "name": "Norte"}, {"id": name + "-south", "name": "Sur"}]}
              for token, name in ((TOKEN_A, "account-a"), (TOKEN_B, "account-b"))}
    controls = {"lose": None, "reject": None, "image_fail": False, "after_write": None}
    data = source()

    def transport(session, method, url, **kwargs):
        token = session.headers.get("Authorization", "").removeprefix("Bearer ")
        assert url.startswith(export.API + "/"), url
        assert kwargs["allow_redirects"] is False
        endpoint = url.removeprefix(export.API + "/").strip("/")
        calls.append({"method": method, "endpoint": endpoint, "token": token, "body": deepcopy(kwargs.get("json"))})
        if token not in states:
            return response({"message": "must-not-leak " + token}, 401)
        state = states[token]
        if method == "GET":
            if endpoint == "merchant":
                return response({"id": state["merchant_id"], "business_name": "Cuenta " + state["merchant_id"]})
            if endpoint == "stores": return response({"stores": state["stores"]})
            if endpoint == "items": return response({"items": list(state["items"].values())})
            if endpoint == "categories": return response({"categories": state["categories"]})
            if endpoint == "variants":
                sku = (kwargs.get("params") or {}).get("sku")
                return response({"variants": [v for item in state["items"].values()
                    for v in item["variants"] if not sku or v["sku"] == sku]})
            if endpoint.startswith("items/"):
                return response(state["items"][endpoint.split("/")[1]])
        if controls["reject"] == endpoint:
            return response({"message": "raw provider header " + token}, 429)
        if endpoint.endswith("/image"):
            assert kwargs["headers"]["Content-Type"] == "image/png"
            if controls["image_fail"]:
                controls["image_fail"] = False
                return response({"message": token}, 503)
            with Image.open(io.BytesIO(kwargs["data"])) as picture:
                assert picture.size == (800, 800) and picture.mode == "RGB"
            state["images"].append(endpoint)
            return response({}, 201)
        body = deepcopy(kwargs.get("json"))
        if endpoint == "categories":
            result = {**body, "id": "cat-" + uid()}
            state["categories"].append(result)
        elif endpoint == "items":
            existing = {v["sku"] for i in state["items"].values() for v in i["variants"]}
            assert not existing.intersection(v["sku"] for v in body["variants"]), "duplicate remote SKU"
            result = {**body, "id": "item-" + uid()}
            result["variants"] = [{**v, "item_id": result["id"], "variant_id": uid()} for v in body["variants"]]
            state["items"][result["id"]] = result
        elif endpoint == "variants":
            assert all(v["sku"] != body["sku"] for i in state["items"].values() for v in i["variants"])
            result = {**body, "variant_id": uid()}
            state["items"][body["item_id"]]["variants"].append(result)
        else:
            raise AssertionError((method, endpoint))
        if controls["after_write"]:
            controls["after_write"]()
        if controls["lose"] == endpoint:
            controls["lose"] = None
            raise requests.Timeout("sensitive " + token)
        return response(result)

    def load(engine, value, images=False):
        engine.ns.update(deepcopy(data))
        if not images: engine.ns["IMAGE_FILES"] = []
        return engine

    monkeypatch.setattr(requests.Session, "request", transport)
    monkeypatch.setattr(export.Exporter, "load", load)
    google_drive = Mock()
    def metadata(**kwargs):
        match = next((f for f in data["IMAGE_FILES"] if f["id"] == kwargs["fileId"]), {})
        return SimpleNamespace(execute=lambda: {**match, "mimeType": "image/jpeg", "parents": [export.FOLDER_ID]})
    google_drive.files().get.side_effect = metadata
    monkeypatch.setattr(export, "google_clients", lambda value: (None, google_drive))
    monkeypatch.setattr(export.time, "sleep", lambda _: None)
    monkeypatch.setattr(redis_broker, "publish_one", Mock())
    monkeypatch.setattr(redis_broker, "reachable", lambda: True)
    monkeypatch.setattr(worker_wakeup, "notify", Mock())
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "rq")
    monkeypatch.setenv("IMAGE_WORKER_ORIGIN", "https://rincon-worker.onrender.com")
    return SimpleNamespace(client=client, value=value, drive=drive, states=states, calls=calls, controls=controls, source=data)


def connect(env, token=TOKEN_A, name="Principal", old=None):
    result = env.client.post("/api/loyverse/connections/test", json={"token": token, "connection_id": old}, headers=ORIGIN)
    assert result.status_code == 200, result.text
    assert token not in result.text
    tested = result.json()
    result = env.client.post("/api/loyverse/connections", json={"test_token": tested["test_token"],
        "name": name, "store_id": tested["stores"][0]["id"], "connection_id": old}, headers=ORIGIN)
    assert result.status_code == 200, result.text
    return result.json()["connection"]


def preview(env, connection, selections=None, images=False, store=None, create_categories=False):
    response = env.client.post("/api/loyverse/preview", json={"connection_id": connection["id"],
        "store_id": store or connection["default_store_id"], "selections": selections or [{"kind": "simple", "sku": "S1"}],
        "options": {"images": images, "create_categories": create_categories}}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return response.json()


def submit(env, reviewed, key=None, confirmation="PUBLICAR"):
    return env.client.post("/api/loyverse/jobs", json={"preview_token": reviewed["preview_token"],
        "request_key": key or uid(), "confirmation": confirmation}, headers=ORIGIN)


def run(env, reviewed):
    accepted = submit(env, reviewed)
    assert accepted.status_code == 202, accepted.text
    jobs = accepted.json()["jobs"]
    for job in jobs: worker.execute_job(job["id"])
    return env.client.get("/api/loyverse/jobs").json()["jobs"][0]


def control(env, job, action, confirmation="PUBLICAR"):
    return env.client.post("/api/loyverse/jobs/" + job["id"] + "/control",
                           json={"action": action, "confirmation": confirmation}, headers=ORIGIN)


def test_all_23_functions_are_unchanged_from_supplied_colab():
    manifest = json.loads(Path("tests/fixtures/loyverse_colab_manifest.json").read_text())
    text = export.CORE.read_text()
    functions = {n.name: hashlib.sha256(ast.get_source_segment(text, n).encode()).hexdigest()
                 for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    assert len(functions) == 23 and functions == manifest["functions"]


def test_connections_must_be_tested_and_credentials_remain_encrypted(loyverse):
    env = loyverse
    assert env.client.post("/api/loyverse/connections", json={"name": "x", "store_id": "x",
        "test_token": "x" * 40}, headers=ORIGIN).status_code == 422
    connection = connect(env)
    assert connection["status"] == "connected" and len(connection["stores"]) == 2
    assert TOKEN_A not in str(env.value)  # Even pending tests contain ciphertext only.
    listed = env.client.get("/api/loyverse/connections")
    assert TOKEN_A not in listed.text and "token" not in listed.text
    with transaction() as db:
        rows = db.scalars(select(IntegrationAccount).where(IntegrationAccount.tenant_id == env.value["platform_tenant"])).all()
        assert all(TOKEN_A not in row.encrypted_credentials for row in rows)
    assert all(c["method"] == "GET" for c in env.calls)


def test_invalid_token_response_is_not_reflected(loyverse):
    result = loyverse.client.post("/api/loyverse/connections/test", json={"token": "invalid-secret"}, headers=ORIGIN)
    assert result.status_code == 502 and "invalid-secret" not in result.text and "must-not-leak" not in result.text


def test_actor_tenant_and_admin_permissions_are_enforced(loyverse):
    env = loyverse
    connection = connect(env)
    reviewed = preview(env, connection)
    job = submit(env, reviewed).json()["jobs"][0]
    env.value["email"] = "editor@example.test"
    assert env.client.get("/api/loyverse/connections").json()["connections"] == []
    assert env.client.get("/api/loyverse/jobs").json()["jobs"] == []
    assert env.client.post("/api/loyverse/connections/test", json={"token": TOKEN_A}, headers=ORIGIN).status_code == 403
    assert control(env, job, "retry").status_code == 403
    env.value["email"] = "admin@example.test"
    env.value["platform_tenant"] = "another-catalog"
    assert env.client.get("/api/loyverse/connections").json()["connections"] == []
    assert env.client.get("/api/loyverse/jobs/" + job["id"] + "/log").status_code == 404


def test_simple_confirmation_idempotency_and_no_image_generation(loyverse, monkeypatch):
    env = loyverse
    connection = connect(env)
    reviewed = preview(env, connection)
    assert all(c["method"] == "GET" for c in env.calls)
    assert submit(env, reviewed, confirmation="").status_code == 422
    key = uid()
    accepted = submit(env, reviewed, key)
    assert accepted.status_code == 202, accepted.text
    job = accepted.json()["jobs"][0]
    assert submit(env, reviewed, key).json()["batch_id"] == accepted.json()["batch_id"]
    assert not env.states[TOKEN_A]["items"]
    maker = Mock(side_effect=AssertionError("Publication must not generate images"))
    monkeypatch.setattr(worker, "generation", maker)
    worker.execute_job(job["id"])
    finished = env.client.get("/api/loyverse/jobs").json()["jobs"][0]
    assert finished["status"] == "completed", finished
    assert finished["log_saved"]
    item = next(iter(env.states[TOKEN_A]["items"].values()))
    variant = item["variants"][0]
    assert variant["barcode"] == "001234567890" and variant["default_price"] == 35.5
    assert variant["stores"] == [{"store_id": "account-a-north", "available_for_sale": True},
                                 {"store_id": "account-a-south", "available_for_sale": False}]
    assert "Marca: Glico" in item["description"] and "Texto largo" in item["description"]
    assert all(c["endpoint"] != "inventory" and "in_stock" not in str(c["body"]) for c in env.calls)
    assert TOKEN_A not in env.client.get("/api/platform/jobs").text
    assert TOKEN_A not in env.client.get("/api/loyverse/jobs/" + job["id"] + "/log").text
    maker.assert_not_called()
    worker.execute_job(job["id"])
    assert len(env.states[TOKEN_A]["items"]) == 1


def test_accounts_can_share_sku_and_jobs_freeze_original_destination(loyverse):
    env = loyverse
    a, b = connect(env), connect(env, TOKEN_B, "Otra cuenta")
    reviewed_a = preview(env, a, store="account-a-south")
    job_a = submit(env, reviewed_a).json()["jobs"][0]
    job_b = submit(env, preview(env, b)).json()["jobs"][0]
    # A new connection/default selection doesn't route the already queued job elsewhere.
    connect(env, TOKEN_A, "Nombre actualizado", old=a["id"])
    worker.execute_job(job_b["id"])
    worker.execute_job(job_a["id"])
    assert len(env.states[TOKEN_A]["items"]) == len(env.states[TOKEN_B]["items"]) == 1
    a_variant = next(iter(env.states[TOKEN_A]["items"].values()))["variants"][0]
    assert next(s["available_for_sale"] for s in a_variant["stores"] if s["store_id"] == "account-a-south")
    assert env.client.post("/api/loyverse/preview", json={"connection_id": a["id"], "store_id": "account-b-north",
        "selections": [{"kind": "simple", "sku": "S1"}]}, headers=ORIGIN).status_code == 422


def test_rotating_connection_cannot_change_merchant_or_reuse_old_preview(loyverse):
    env = loyverse
    a = connect(env)
    reviewed = preview(env, a)
    connect(env, old=a["id"])
    assert submit(env, reviewed).status_code == 409
    test = env.client.post("/api/loyverse/connections/test", json={"token": TOKEN_B, "connection_id": a["id"]}, headers=ORIGIN).json()
    response = env.client.post("/api/loyverse/connections", json={"test_token": test["test_token"], "connection_id": a["id"],
        "name": "wrong", "store_id": "account-b-north"}, headers=ORIGIN)
    assert response.status_code == 409


def test_comparison_filters_and_remote_catalog_are_read_only(loyverse):
    env = loyverse
    a = connect(env)
    run(env, preview(env, a))
    params = {"connection_id": a["id"], "store_id": a["default_store_id"]}
    result = env.client.get("/api/loyverse/catalog", params={**params, "q": "S1", "brand": "Glico", "kind": "simple"})
    assert result.status_code == 200, result.text
    assert [r["comparison"] for r in result.json()["rows"]] == ["existing"]
    assert result.json()["summary"]["missing"] == 3
    remote = env.client.get("/api/loyverse/catalog", params={**params, "remote": True}).json()["rows"]
    assert [r["sku"] for r in remote] == ["S1"] and remote[0]["available"]
    assert "item_id" not in str(remote) and "variant_id" not in str(remote)


def test_existing_simple_stock_price_and_image_are_untouched(loyverse):
    env = loyverse
    a = connect(env)
    run(env, preview(env, a))
    item = next(iter(env.states[TOKEN_A]["items"].values()))
    item["variants"][0].update(default_price=99, in_stock=22)
    original = deepcopy(item)
    env.calls.clear()
    result = run(env, preview(env, a, images=True))
    assert result["status"] == "completed"
    assert item == original and not any(c["method"] == "POST" for c in env.calls)


def test_family_and_individual_variants_preserve_existing_variant(loyverse):
    env = loyverse
    a = connect(env)
    result = run(env, preview(env, a, [{"kind": "variant", "sku": "V1"}]))
    assert result["status"] == "completed", result
    parent = next(iter(env.states[TOKEN_A]["items"].values()))
    assert parent["reference_id"] == "F1" and len(parent["variants"]) == 1
    parent["variants"][0].update(default_price=199, in_stock=8)
    existing = deepcopy(parent["variants"][0])
    result = run(env, preview(env, a, [{"kind": "family", "sku": "F1"}]))
    assert result["status"] == "completed", result
    assert len(env.states[TOKEN_A]["items"]) == 1
    assert {v["sku"] for v in parent["variants"]} == {"V1", "V2"}
    assert parent["variants"][0] == existing
    assert parent["option1_name"] == "Sabor" and "option2_name" not in parent


def test_overlapping_bulk_selection_is_normalized_and_each_job_bounded(loyverse):
    env = loyverse
    a = connect(env)
    selected = [{"kind": "family", "sku": "F1"}, {"kind": "variant", "sku": "V1"},
                {"kind": "simple", "sku": "S1"}, {"kind": "simple", "sku": "S1"}]
    reviewed = preview(env, a, selected)
    assert len(reviewed["previews"]) == 2 and len(reviewed["omitted"]) == 1
    accepted = submit(env, reviewed).json()
    assert len(accepted["jobs"]) == 2
    with transaction() as db:
        for public in accepted["jobs"]:
            job = db.get(GenerationJob, public["id"])
            assert job.payload["source"]["SIMPLES"].keys() <= {"S1"}
            assert "token" not in job.payload
            assert job.payload["connection_id"] == a["id"]
            assert job.payload["store_id"] == a["default_store_id"]


def test_wrong_family_incompatible_attribute_and_deleted_sku_block_preview(loyverse):
    env = loyverse
    a = connect(env)
    run(env, preview(env, a, [{"kind": "family", "sku": "F1"}]))
    parent = next(iter(env.states[TOKEN_A]["items"].values()))
    parent["option1_name"] = "Tamaño"
    reviewed = preview(env, a, [{"kind": "variant", "sku": "V1"}])
    assert reviewed["errors"] and submit(env, reviewed).status_code == 422
    parent["option1_name"] = "Sabor"
    parent["variants"][0]["deleted_at"] = "2026-10-01"
    reviewed = preview(env, a, [{"kind": "variant", "sku": "V1"}])
    assert "eliminado" in reviewed["errors"][0]["message"]


def test_lost_create_response_is_reconciled_before_retry_without_duplicates(loyverse):
    env = loyverse
    a = connect(env)
    env.controls["lose"] = "items"
    failed = run(env, preview(env, a))
    assert failed["status"] == "failed" and failed["uncertain"], failed
    assert TOKEN_A not in str(failed) and len(env.states[TOKEN_A]["items"]) == 1
    # The generic image retry route must not bypass connection/attempt/confirmation guards.
    assert env.client.post("/api/platform/jobs/" + failed["id"] + "/retry", json={
        "confirm": True, "uncertainty_reviewed": True, "request_key": uid()}, headers=ORIGIN).status_code == 409
    assert control(env, failed, "retry", "").status_code == 422
    assert control(env, failed, "retry").status_code == 200
    worker.execute_job(failed["id"])
    done = env.client.get("/api/loyverse/jobs").json()["jobs"][0]
    assert done["status"] == "completed" and not done["uncertain"], done
    assert len(env.states[TOKEN_A]["items"]) == 1
    assert sum(c["method"] == "POST" and c["endpoint"] == "items" for c in env.calls) == 1


def test_three_attempt_limit_and_no_blind_post_retry(loyverse):
    env = loyverse
    a = connect(env)
    env.controls["reject"] = "items"
    failed = run(env, preview(env, a))
    for _ in range(2):
        assert control(env, failed, "retry").status_code == 200
        worker.execute_job(failed["id"])
    assert control(env, failed, "retry").status_code == 422
    assert sum(c["method"] == "POST" for c in env.calls) == 3
    assert not env.states[TOKEN_A]["items"]


def test_pause_resume_cancel_and_connection_deletion(loyverse):
    env = loyverse
    a = connect(env)
    queued = submit(env, preview(env, a)).json()["jobs"][0]
    assert control(env, queued, "pause").json()["job"]["status"] == "paused"
    worker.execute_job(queued["id"])
    assert not env.states[TOKEN_A]["items"]
    assert control(env, queued, "resume", "").status_code == 422
    assert control(env, queued, "resume").json()["job"]["status"] == "queued"
    assert control(env, queued, "pause").status_code == 200
    assert env.client.delete("/api/loyverse/connections/" + a["id"], headers=ORIGIN).status_code == 200
    job = env.client.get("/api/loyverse/jobs").json()["jobs"][0]
    assert job["status"] == "cancelled"
    worker.execute_job(job["id"])
    assert not env.states[TOKEN_A]["items"]
    with transaction() as db:
        from catalog_platform.accounts import account
        assert account(db, env.value["platform_tenant"], job["id"], JOB_PROVIDER).status == "disconnected"


def test_active_pause_preserves_acknowledged_result_and_resumes_safely(loyverse):
    env = loyverse
    a = connect(env)
    job = submit(env, preview(env, a)).json()["jobs"][0]
    env.controls["after_write"] = lambda: control(env, job, "pause")
    worker.execute_job(job["id"])
    paused = env.client.get("/api/loyverse/jobs").json()["jobs"][0]
    assert paused["status"] == "paused" and not paused["uncertain"], paused
    assert len(env.states[TOKEN_A]["items"]) == 1
    env.controls["after_write"] = None
    control(env, job, "resume")
    worker.execute_job(job["id"])
    assert env.client.get("/api/loyverse/jobs").json()["jobs"][0]["status"] == "completed"
    assert len(env.states[TOKEN_A]["items"]) == 1


def test_image_failure_retries_only_main_image_without_recreating_item(loyverse, monkeypatch):
    env = loyverse
    picture = Image.new("RGBA", (180, 300), (200, 0, 0, 100))
    buffer = io.BytesIO(); picture.save(buffer, "PNG"); raw = buffer.getvalue()
    class Download:
        def __init__(self, stream, request, **kwargs): self.stream = stream
        def next_chunk(self): self.stream.write(raw); return None, True
    import googleapiclient.http
    monkeypatch.setattr(googleapiclient.http, "MediaIoBaseDownload", Download)
    env.source["IMAGE_FILES"] = [
        {"id": "original", "name": "S1_2_uso.jpg", "size": "100"},
        {"id": "final", "name": "S1_1_hd.jpg", "size": "100"}]
    a = connect(env)
    reviewed = preview(env, a, images=True)
    assert reviewed["previews"][0]["items"][0]["image_name"] == "S1_1_hd.jpg"
    assert "id=" not in reviewed["previews"][0]["items"][0]["image_url"]
    env.controls["image_fail"] = True
    failed = run(env, reviewed)
    assert failed["status"] == "failed", failed
    assert len(env.states[TOKEN_A]["items"]) == 1
    control(env, failed, "retry")
    worker.execute_job(failed["id"])
    done = env.client.get("/api/loyverse/jobs").json()["jobs"][0]
    assert done["status"] == "completed", done
    assert len(env.states[TOKEN_A]["images"]) == 1 and len(env.states[TOKEN_A]["items"]) == 1


def test_rq_uses_publication_queue_only_job_id_and_keeps_image_priority(loyverse, monkeypatch):
    env = loyverse
    a = connect(env)
    redis = fakeredis.FakeRedis(version=(7, 0))
    from test_woocommerce_queue import PUBLISH_ONE
    monkeypatch.setattr(redis_broker, "connection", lambda: redis)
    monkeypatch.setattr(redis_broker, "publish_one", PUBLISH_ONE)
    result = submit(env, preview(env, a))
    assert result.status_code == 202, result.text
    target = redis_broker.rq_queue("loyverse_export")
    assert target.count == 1 and redis_broker.rq_queue().count == 0
    assert list(target.jobs[0].args) == [result.json()["jobs"][0]["id"]]
    assert TOKEN_A not in target.jobs[0].data.decode()
    ControlledWorker([redis_broker.rq_queue(), target], connection=redis,
        serializer=JSONSerializer).work(burst=True, logging_level="WARNING")
    assert env.client.get("/api/loyverse/jobs").json()["jobs"][0]["status"] == "completed"


def test_http_boundary_blocks_foreign_hosts_deletes_stock_and_existing_price_updates(loyverse):
    session = export.LoyverseSession(TOKEN_A, write=True, store_id="account-a-north", stores=["account-a-north"])
    for method, url, payload in [("POST", "https://evil.example/items", {}),
            ("DELETE", export.API + "/items/item-id", {}),
            ("POST", export.API + "/inventory", {}),
            ("POST", export.API + "/variants", {"variant_id": "existing", "default_price": 1})]:
        with pytest.raises(ValueError): session.request(method, url, json=payload)
    assert not loyverse.calls


def test_read_retries_bounded_and_pagination_loop_is_detected(monkeypatch):
    calls = []
    def http(session, method, url, **kwargs):
        calls.append(1)
        if len(calls) < 3: return response({}, 429)
        return response({"items": [], "cursor": "repeating"})
    monkeypatch.setattr(requests.Session, "request", http)
    monkeypatch.setattr(export.time, "sleep", lambda _: None)
    engine = export.Exporter(TOKEN_A)
    with pytest.raises(RuntimeError, match="Paginación repetida"):
        engine.ns["listar"]("items", "items")
    assert len(calls) == 4


def test_download_and_source_duplicate_bounds():
    stream = export.LimitedBuffer()
    stream.seek(export.MAX_IMAGE)
    with pytest.raises(ValueError): stream.write(b"a")
    with pytest.raises(ValueError, match="SKU duplicado"):
        export.keyed([{"sku": "S1"}, {"sku": "S1"}], "sku")


def test_large_family_is_split_into_small_jobs_without_changing_core(loyverse):
    env = loyverse
    env.source["VARIANTES"] = {}
    for index in range(111):
        sku = "CHILD" + str(index)
        env.source["VARIANTES"][sku] = {**source()["VARIANTES"]["V1"], "sku": sku}
        env.source["CSV_V"][sku] = {"Nombre del atributo 1": "Sabor", "Valor(es) del atributo 1": "Opción " + str(index)}
    a = connect(env)
    result = submit(env, preview(env, a, [{"kind": "family", "sku": "F1"}]))
    assert result.status_code == 202, result.text
    jobs = result.json()["jobs"]
    assert len(jobs) == 3
    with transaction() as db:
        sizes = [len(db.get(GenerationJob, j["id"]).payload["source"]["VARIANTES"]) for j in jobs]
        assert sizes == [50, 50, 11]
    for job in jobs: worker.execute_job(job["id"])
    assert len(env.states[TOKEN_A]["items"]) == 1
    assert len(next(iter(env.states[TOKEN_A]["items"].values()))["variants"]) == 111


def test_drive_log_failure_keeps_sql_results_and_download(loyverse, monkeypatch):
    env = loyverse
    monkeypatch.setattr(env.drive, "upload_bytes", Mock(side_effect=ValueError("Drive unavailable")))
    result = run(env, preview(env, connect(env)))
    assert result["status"] == "completed" and not result["log_saved"]
    download = env.client.get("/api/loyverse/jobs/" + result["id"] + "/log")
    assert download.status_code == 200 and download.json()["events"]


def test_job_history_paginates_without_losing_account_scope_or_global_counts(loyverse):
    env = loyverse
    a = connect(env)
    reviewed = preview(env, a)
    ids = {submit(env, reviewed).json()["jobs"][0]["id"] for _ in range(3)}
    rows = []
    for offset in range(3):
        page = env.client.get("/api/loyverse/jobs", params={"offset": offset, "limit": 1}).json()
        assert page["total"] == 3 and page["summary"] == {"queued": 3}
        assert len(page["jobs"]) == 1
        rows.append(page["jobs"][0]["id"])
    assert set(rows) == ids and len(set(rows)) == 3
    assert env.client.get("/api/loyverse/jobs", params={"offset": 3, "limit": 1}).json()["jobs"] == []
    env.value["email"] = "editor@example.test"
    empty = env.client.get("/api/loyverse/jobs").json()
    assert empty == {"jobs": [], "total": 0, "summary": {}}


def test_ambiguous_reference_and_second_remote_attribute_are_blocked(loyverse):
    env = loyverse
    a = connect(env)
    run(env, preview(env, a, [{"kind": "family", "sku": "F1"}]))
    item = next(iter(env.states[TOKEN_A]["items"].values()))
    item["option2_name"] = "Tamaño"
    assert preview(env, a, [{"kind": "family", "sku": "F1"}])["errors"]
    del item["option2_name"]
    env.states[TOKEN_A]["items"]["duplicate-reference"] = {**item, "id": "duplicate-reference", "variants": []}
    reviewed = preview(env, a, [{"kind": "family", "sku": "F1"}])
    assert "más de un artículo" in reviewed["errors"][0]["message"]


def test_image_index_excludes_private_names_and_nested_files(monkeypatch):
    from drive_service import DriveService
    google = Mock()
    google.files().get().execute.return_value = {"name": "imagenes_generadas", "mimeType": "application/vnd.google-apps.folder"}
    def file(name, parent=export.FOLDER_ID):
        return {"id": name, "name": name, "parents": [parent], "mimeType": "image/jpeg"}
    monkeypatch.setattr(DriveService, "list", lambda *args, **kwargs: [file("S1_1_hd.jpg"),
        file("S1_2_uso.jpg"), file("S1_raw.jpg"), file("S1_reference.jpg"), file("S1_1.png", "private-folder")])
    assert [f["name"] for f in export.index_images(google)] == ["S1_1_hd.jpg", "S1_2_uso.jpg"]


def test_worker_does_not_download_image_moved_to_private_folder():
    google = Mock()
    google.files().get().execute.return_value = {"name": "S1_1_hd.jpg", "parents": ["private"], "mimeType": "image/jpeg"}
    proxy = export.ImageDrive(google, [{"id": "file", "name": "S1_1_hd.jpg"}])
    with pytest.raises(ValueError, match="carpeta"):
        proxy.get_media("file")
    google.files().get_media.assert_not_called()


def test_postgres_serializes_same_account_across_different_connections(loyverse):
    import os
    if not os.getenv("TEST_DATABASE_URL", "").startswith("postgres"):
        pytest.skip("Requires dedicated PostgreSQL, exercised by CI")
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from catalog_platform.loyverse_jobs import enqueue
    env = loyverse
    a = connect(env)
    other = connect(env, TOKEN_A, "Otra conexión de la misma cuenta")
    reviewed = preview(env, a)
    # Submit distinct jobs with an identical SKU; provider-side duplicate assertion is intentional.
    first = submit(env, reviewed).json()["jobs"][0]
    second = submit(env, preview(env, other)).json()["jobs"][0]
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(worker.execute_job, [first["id"], second["id"]]))
    results = env.client.get("/api/loyverse/jobs").json()["jobs"]
    assert all(r["status"] == "completed" for r in results), results
    assert len(env.states[TOKEN_A]["items"]) == 1
