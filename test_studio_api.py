"""Real HTTP studio flow with provider/Drive doubles; never spends API credits."""
import io
import os
from pathlib import Path
import secrets
import threading
import time
from unittest.mock import Mock

os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "https://suite.example/auth/callback")

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import service_entrypoint
import studio_api as studio
from creative_pipeline import fallback_brief

ORIGIN = {"Origin": "https://suite.example"}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://suite.example")
    sid = secrets.token_urlsafe(24)
    value = {"session_id": sid, "expires_at": time.time()+600,
             "file_namespace": secrets.token_urlsafe(24), "gemini_key": "test-key-with-no-live-credits"}
    studio.runtime.SESSIONS[sid] = value
    client = TestClient(service_entrypoint.fastapi_app, base_url="https://suite.example")
    client.cookies.set("session_id", sid)
    yield client, value
    studio.runtime._eliminar_sesion(sid)
    client.close()


def upload(client):
    data = io.BytesIO()
    Image.new("RGB", (120, 180), "red").save(data, "PNG")
    response = client.post("/api/uploads", files={"image": ("product.png", data.getvalue(), "image/png")}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def prepare(client):
    key = upload(client)
    response = client.post("/api/capture", json={"front_id": key, "context": "Pocky de chocolate"}, headers=ORIGIN)
    assert response.status_code == 200
    product = studio.Product(sku="POCK41", name="Pocky chocolate", brand="Glico", size="41 g", category="Dulces").model_dump()
    assert client.put("/api/draft", json=product, headers=ORIGIN).status_code == 200
    return key


def wait(client, response):
    assert response.status_code == 202, response.text
    key = response.json()["job"]["id"]
    deadline = time.monotonic()+5
    while time.monotonic() < deadline:
        result = client.get("/api/jobs/"+key)
        assert result.status_code == 200, result.text
        data = result.json()
        if data["job"]["status"] not in {"queued", "running"}:
            return data
        threading.Event().wait(.02)
    raise AssertionError("Test job did not finish")


def provider(monkeypatch):
    image = Image.new("RGB", (1024, 1024), "purple")
    ImageDraw.Draw(image).rectangle((350, 200, 680, 880), fill="orange")
    maker = Mock(return_value=image)
    planner = Mock(side_effect=lambda client, product, paths: fallback_brief(product))
    monkeypatch.setattr(studio, "generate", maker)
    monkeypatch.setattr(studio, "brief", planner)
    monkeypatch.setattr(studio, "load_style_examples", lambda *a: ([], ""))
    return maker, planner


def test_auth_csrf_and_upload_ownership(setup):
    client, value = setup
    client.cookies.clear()
    assert client.get("/api/session").json()["authenticated"] is False
    assert client.get("/api/draft").status_code == 401
    assert client.post("/api/capture", json={"front_id": "missing"}).status_code == 403
    client.cookies.set("session_id", value["session_id"])
    key = upload(client)
    assert client.get("/api/files/"+key).status_code == 200
    assert client.get("/api/files/"+key).headers["cache-control"] == "no-store"
    assert "/tmp/" not in client.get("/api/session").text
    assert value["gemini_key"] not in client.get("/api/session").text
    sid = secrets.token_urlsafe(24)
    studio.runtime.SESSIONS[sid] = {"session_id": sid, "expires_at": time.time()+600}
    try:
        client.cookies.set("session_id", sid)
        assert client.get("/api/files/"+key).status_code == 404
        assert client.post("/api/capture", json={"front_id": key}, headers=ORIGIN).status_code == 404
    finally:
        studio.runtime._eliminar_sesion(sid)


def test_generation_edit_history_single_plan_and_explicit_save(setup, monkeypatch):
    client, value = setup
    prepare(client)
    maker, planner = provider(monkeypatch)
    writer = Mock(return_value="💾 Producto guardado en Drive")
    qa = Mock(return_value={"aprobada": True})
    monkeypatch.setattr(studio.runtime.captura, "save", writer)
    monkeypatch.setattr(studio.runtime, "_validar_con_vision", qa)
    result = wait(client, client.post("/api/generate", json={"slots": ["2_uso", "3_comercial"]}, headers=ORIGIN))
    assert result["job"]["status"] == "completed"
    assert len(result["draft"]["images"]) == 2
    assert maker.call_count == 2
    planner.assert_called_once()
    qa.assert_not_called()
    writer.assert_not_called()
    assert not any(picture["approved"] for picture in result["draft"]["images"].values())
    previous = value["studio_draft"]["images"]["2_uso"]["raw_id"]
    result = wait(client, client.post("/api/images/2_uso/correct", json={"feedback": "Sostener el paquete con la mano derecha"}, headers=ORIGIN))
    assert result["job"]["status"] == "completed"
    assert maker.call_args.kwargs["previous"] == studio.file_path(value, previous)
    assert "mano derecha" in maker.call_args.kwargs["corrections"][0]
    assert maker.call_args.args[1] == value["studio_draft"]["references"]
    assert planner.call_count == 1
    assert client.post("/api/save", json={"confirm": True}, headers=ORIGIN).status_code == 409
    for slot in ("2_uso", "3_comercial"):
        assert client.post(f"/api/images/{slot}/approve", json={"approved": True}, headers=ORIGIN).status_code == 200
    assert client.post("/api/save", json={"confirm": False}, headers=ORIGIN).status_code == 422
    result = wait(client, client.post("/api/save", json={"confirm": True}, headers=ORIGIN))
    assert result["draft"]["saved"].startswith("💾")
    assert client.post("/api/save", json={"confirm": True}, headers=ORIGIN).status_code == 200
    writer.assert_called_once()


def test_failed_correction_preserves_previous_and_feedback(setup, monkeypatch):
    client, value = setup
    prepare(client)
    maker, planner = provider(monkeypatch)
    first = wait(client, client.post("/api/generate", json={"slots": ["2_uso"]}, headers=ORIGIN))
    previous = first["draft"]["images"]["2_uso"]["id"]
    maker.side_effect = ValueError("Gemini no devolvió una imagen")
    result = wait(client, client.post("/api/images/2_uso/correct", json={"feedback": "Mantener el empaque rojo"}, headers=ORIGIN))
    assert result["job"]["status"] == "failed"
    assert result["draft"]["images"]["2_uso"]["id"] == previous
    assert result["draft"]["images"]["2_uso"]["history"] == ["Mantener el empaque rojo"]
    assert client.get("/api/files/"+previous).status_code == 200
    assert maker.call_count == 2  # No automatic paid retry.
    assert planner.call_count == 1


def test_hd_skips_research_and_optional_qa_never_deletes_candidate(setup, monkeypatch):
    client, value = setup
    prepare(client)
    maker, planner = provider(monkeypatch)
    qa = Mock(return_value={"aprobada": False, "resumen": "Revisar el color"})
    monkeypatch.setattr(studio.runtime, "_validar_con_vision", qa)
    result = wait(client, client.post("/api/generate", json={"slots": ["1_hd"], "automatic_review": True}, headers=ORIGIN))
    assert result["job"]["status"] == "completed"
    assert result["draft"]["images"]["1_hd"]["id"]
    assert result["draft"]["images"]["1_hd"]["approved"] is False
    assert result["draft"]["images"]["1_hd"]["qa"]["aprobada"] is False
    planner.assert_not_called()
    qa.assert_called_once()
    maker.assert_called_once()


def test_job_progress_recovers_and_conflicting_work_is_blocked(setup, monkeypatch):
    client, value = setup
    prepare(client)
    started, release = threading.Event(), threading.Event()
    def blocked(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return Image.new("RGB", (1024,1024), "purple")
    monkeypatch.setattr(studio, "generate", blocked)
    response = client.post("/api/generate", json={"slots": ["1_hd"]}, headers=ORIGIN)
    assert started.wait(2)
    try:
        assert client.get("/api/session").json()["job"]["id"] == response.json()["job"]["id"]
        assert client.post("/api/generate", json={"slots": ["1_hd"]}, headers=ORIGIN).status_code == 409
        assert client.put("/api/draft", json=studio.Product().model_dump(), headers=ORIGIN).status_code == 409
        sid = secrets.token_urlsafe(24)
        studio.runtime.SESSIONS[sid] = {"session_id": sid, "expires_at": time.time()+600}
        client.cookies.set("session_id", sid)
        assert client.get("/api/jobs/"+response.json()["job"]["id"]).status_code == 404
        studio.runtime._eliminar_sesion(sid)
        client.cookies.set("session_id", value["session_id"])
    finally:
        release.set()
    assert wait(client, response)["job"]["status"] == "completed"


def test_invalid_upload_and_logout_remove_private_files(setup):
    client, value = setup
    assert client.post("/api/uploads", files={"image": ("data.svg", b"<svg/>", "image/svg+xml")}, headers=ORIGIN).status_code == 422
    key = upload(client)
    path = Path(studio.file_path(value, key))
    assert client.post("/logout", headers=ORIGIN, follow_redirects=False).status_code == 303
    assert not path.exists()
    assert client.get("/api/files/"+key).status_code == 401
