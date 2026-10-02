import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.update(GOOGLE_CLIENT_ID="test", GOOGLE_CLIENT_SECRET="test",
                  GOOGLE_REDIRECT_URI="https://suite.example/auth/callback",
                  GRADIO_ANALYTICS_ENABLED="False")
import app_security as security
import gemini_gateway as gateway
import app
import server
from fastapi.testclient import TestClient
from google.genai import types
from woocommerce_client import WooCommerceClient, WooCommerceConfig, WooCommerceError, NoRedirect


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    gateway._cache.clear()
    gateway._budgets.clear()
    security.OAUTH_STATES.clear()
    monkeypatch.delenv("WC_ALLOWED_EMAILS", raising=False)
    monkeypatch.delenv("APP_ALLOWED_EMAILS", raising=False)
    yield
    for sid in list(security.SESSIONS):
        security.drop_session(sid)


def test_oauth_state_is_bound_expiring_and_single_use():
    security.issue_oauth("correct", "verifier")
    with pytest.raises(ValueError):
        security.consume_oauth("correct", "attacker")
    assert security.consume_oauth("correct", "correct") == "verifier"
    with pytest.raises(ValueError):
        security.consume_oauth("correct", "correct")
    security.OAUTH_STATES["old"] = (time.time() - 1, "v")
    with pytest.raises(ValueError):
        security.consume_oauth("old", "old")


def test_sessions_expire_and_remove_private_files():
    security.create_session("a", email="a@example.com")
    session = security.get_session("a")
    path = Path(security.session_path(session))
    path.write_bytes(b"private")
    session["expires_at"] = 0
    assert security.get_session("a") is None
    assert not path.exists()


def test_paths_cannot_cross_sessions_or_traverse():
    for sid in ("a", "b"):
        security.create_session(sid)
    other = Path(security.session_path(security.get_session("b")))
    other.write_bytes(b"secret")
    with pytest.raises(ValueError):
        security.owned_paths(security.get_session("a"), [str(other)])
    with pytest.raises(ValueError):
        security.owned_paths(security.get_session("a"), ["../../etc/passwd"])


def test_routes_auth_csrf_and_wc_access(monkeypatch):
    with TestClient(server.fastapi_app, base_url="https://suite.example") as client:
        assert client.get("/healthz").status_code == 200
        assert "Conectar" in client.get("/").text
        for path in ("/wc-health", "/wc-preview", "/inventory-sync", "/gradio_api/file=/etc/passwd"):
            assert client.get(path).status_code == 401
        security.create_session("sid", email="allowed@example.com")
        client.cookies.set("session_id", "sid")
        assert client.get("/wc-health").status_code == 403
        monkeypatch.setenv("WC_ALLOWED_EMAILS", "allowed@example.com")
        monkeypatch.setattr(server, "_connection_test", lambda: {"ok": True})
        assert client.get("/wc-health").json() == {"ok": True}
        assert client.get("/wc-preview?limit=0").status_code == 422
        assert client.post("/logout", headers={"origin": "https://evil.example"}).status_code == 403
        assert security.get_session("sid")
        response = client.post("/logout", headers={"origin": "https://suite.example"}, follow_redirects=False)
        assert response.status_code == 303
        assert not security.get_session("sid")


def test_invalid_oauth_does_not_exchange_token(monkeypatch):
    flow = MagicMock()
    monkeypatch.setattr(app.Flow, "from_client_config", flow)
    with TestClient(server.fastapi_app, base_url="https://suite.example") as client:
        response = client.get("/auth/callback?code=secret-code&state=bad")
    assert response.status_code == 400
    assert "secret-code" not in response.text
    flow.assert_not_called()


def response(data, finish="STOP"):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(parts=[types.Part(text=json.dumps(data))]), finish_reason=finish)])


def fake_sdk(monkeypatch, result):
    sdk = MagicMock()
    sdk.return_value.__enter__.return_value.models.generate_content.return_value = result
    monkeypatch.setattr(gateway.genai, "Client", sdk)
    return sdk


def test_cache_reuses_identical_requests_but_isolates_keys(monkeypatch):
    sdk = fake_sdk(monkeypatch, response({"lifestyle": "studio"}))
    for key in ("a", "a", "b"):
        gateway.GeminiClient(key).generate_content(model="gemini-2.5-flash", contents="same")
    assert sdk.call_count == 2
    assert sdk.call_args.kwargs["http_options"].retry_options.attempts == 1


def test_truncated_results_are_never_cached(monkeypatch):
    sdk = fake_sdk(monkeypatch, response({"data": "partial"}, "MAX_TOKENS"))
    for _ in range(2):
        with pytest.raises(ValueError):
            gateway.GeminiClient("a").generate_content(model="gemini-2.5-flash", contents="same")
    assert sdk.call_count == 2
    assert not gateway._cache


def test_rate_limit_blocks_paid_call(monkeypatch):
    monkeypatch.setenv("GEMINI_CALLS_PER_MINUTE", "1")
    sdk = fake_sdk(monkeypatch, response({"ok": True}))
    gateway.GeminiClient("a").generate_content(model="gemini-2.5-flash", contents="first")
    with pytest.raises(RuntimeError):
        gateway.GeminiClient("a").generate_content(model="gemini-2.5-flash", contents="second")
    assert sdk.call_count == 1


def test_text_configuration_bounds_output_without_search_json_conflict():
    plain = gateway.text_config(768)
    assert plain.max_output_tokens == 768
    assert plain.thinking_config.thinking_budget == 0
    assert plain.response_mime_type == "application/json"
    search = gateway.text_config(1536, search=True)
    assert search.tools and search.response_mime_type is None


def test_feedback_is_bounded_and_sku_cannot_write_paths():
    _, history, _ = app._construir_correccion([], "x" * 10000, ["y" * 10000] * 100)
    assert len(history) <= 8
    assert sum(map(len, history)) < 5000


def test_woocommerce_requires_https_and_refuses_redirects():
    client = WooCommerceClient(WooCommerceConfig("http://shop.example", "key", "secret"))
    with pytest.raises(WooCommerceError):
        client.list_products()
    with pytest.raises(WooCommerceError):
        NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example")


def test_qa_string_false_never_passes(monkeypatch, tmp_path):
    candidate = tmp_path / "candidate.jpg"
    candidate.write_bytes(b"test")
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(
        {"aprobada": "false", "puntuacion": 99, "errores": []}))
    assert not app._validar_con_vision(client, [], str(candidate), "1_hd")["aprobada"]


def test_login_uses_pkce_and_secure_cookie():
    from urllib.parse import parse_qs, urlsplit
    with TestClient(server.fastapi_app, base_url="https://suite.example") as client:
        result = client.get("/login", follow_redirects=False)
    query = parse_qs(urlsplit(result.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert "Secure" in result.headers["set-cookie"]
    assert "HttpOnly" in result.headers["set-cookie"]


def test_gradio_upload_is_session_scoped():
    import io
    from PIL import Image
    content = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(content, format="JPEG")
    security.create_session("owner", email="owner@example.com")
    security.create_session("other", email="other@example.com")
    with TestClient(server.fastapi_app, base_url="https://suite.example") as client:
        client.cookies.set("session_id", "owner")
        upload = client.post("/gradio_api/upload", headers={"origin": "https://suite.example"},
                             files={"files": ("photo.jpg", content.getvalue(), "image/jpeg")})
        assert upload.status_code == 200, upload.text
        path = upload.json()[0]
        assert client.get("/gradio_api/file=" + path).status_code == 200
        client.cookies.set("session_id", "other")
        assert client.get("/gradio_api/file=" + path).status_code == 403
        with pytest.raises(ValueError):
            security.validate_file_data(security.get_session("other"),
                {"path": path, "meta": {"_type": "gradio.FileData"}})


def test_visual_qa_outage_does_not_generate_more_images(monkeypatch, tmp_path):
    import io
    from PIL import Image
    data = io.BytesIO()
    Image.new("RGB", (1024, 1024)).save(data, format="JPEG")
    source = tmp_path / "source.jpg"
    source.write_bytes(data.getvalue())
    sdk = MagicMock()
    monkeypatch.setattr(app, "GeminiClient", lambda **kwargs: sdk)
    monkeypatch.setattr(app, "_extraer_imagen_bytes", lambda response: data.getvalue())
    monkeypatch.setattr(app, "_validar_con_vision", lambda *args: {"aprobada": False, "technical_error": True})
    monkeypatch.setattr(app, "MAX_INTENTOS_IMAGEN", 3)
    result = app.generar_foto_individual("studio", [str(source)], str(tmp_path / "out.jpg"), "key", None, None, "1_hd")
    assert result["ruta"] is None
    assert result["intentos"] == 1
    assert sdk.models.generate_content.call_count == 1


def test_queue_and_file_payload_cannot_cross_sessions():
    security.create_session("one")
    security.create_session("two")
    first, second = security.get_session("one"), security.get_session("two")
    security.bind_queue_session(first, "browser-tab")
    with pytest.raises(ValueError):
        security.bind_queue_session(second, "browser-tab")
    with pytest.raises(ValueError):
        security.validate_file_data(second, {"data": [{"path": "/etc/passwd"}]})


def test_extraction_includes_tags_without_an_extra_call(monkeypatch):
    import numpy as np
    import pandas as pd
    security.create_session("extract", gemini_key="key")
    session = security.get_session("extract")
    monkeypatch.setattr(app, "_validar_sesion", lambda request: (session, None))
    monkeypatch.setattr(app, "_cargar_df", lambda session: (None, None, pd.DataFrame()))
    result = response({"nombre": "Ramen", "marca": "Marca", "gramaje": "100G",
                       "categoria": "Alimentos", "subcategoria": "Ramen", "desc_corta": "Ramen",
                       "desc_larga": "Ramen de 100 g", "etiquetas": ["ramen"]})
    sdk = MagicMock()
    sdk.models.generate_content.return_value = result
    monkeypatch.setattr(app, "GeminiClient", lambda **kwargs: sdk)
    pricing = MagicMock(return_value={"precio_sugerido": 20})
    monkeypatch.setattr(app, "estimar_precio_producto", pricing)
    tags = MagicMock(side_effect=AssertionError("Unexpected paid tags call"))
    monkeypatch.setattr(app, "estimar_etiquetas_producto", tags)
    output = app.modulo_extraer_textos(np.zeros((32, 32, 3), dtype=np.uint8), None, "ramen", None)
    assert len(output) == 14
    assert output[12] == "ramen"
    assert output[5] == 20
    assert sdk.models.generate_content.call_count == 1
    assert pricing.call_count == 1
    tags.assert_not_called()
