import os, json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
os.environ.update(GOOGLE_CLIENT_ID="test", GOOGLE_CLIENT_SECRET="test", GOOGLE_REDIRECT_URI="https://suite.example/auth/callback", GRADIO_ANALYTICS_ENABLED="False", SUITE_SERVICE_ROLE="main")
import product_web_ai
import app
import gemini_gateway as gateway
import oauth_guard
from google.genai import types

@pytest.fixture(autouse=True)
def clean():
    gateway._cache.clear()
    gateway._budgets.clear()
    oauth_guard._pending.clear()
    yield
    app.SESSIONS.clear()

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

def test_qa_string_false_never_passes(monkeypatch, tmp_path):
    candidate = tmp_path / "candidate.jpg"
    candidate.write_bytes(b"test")
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(
        {"aprobada": "false", "puntuacion": 99, "errores": []}))
    assert not app._validar_con_vision(client, [], str(candidate), "1_hd")["aprobada"]


def test_production_extraction_combines_tags(monkeypatch):
    import numpy as np
    import pandas as pd
    session = {"session_id": "test", "gemini_key": "key"}
    monkeypatch.setattr(app, "_validar_sesion", lambda request: (session, None))
    monkeypatch.setattr(app, "_cargar_df", lambda session: (None, None, pd.DataFrame()))
    sdk = MagicMock()
    sdk.models.generate_content.return_value = response({
        "nombre": "Ramen", "marca": "Marca", "gramaje": "100G", "categoria": "Alimentos",
        "subcategoria": "Ramen", "desc_corta": "Ramen", "desc_larga": "100 g", "etiquetas": ["ramen"]})
    monkeypatch.setattr(app, "GeminiClient", lambda **kwargs: sdk)
    pricing = MagicMock(return_value={"precio_sugerido": 20})
    monkeypatch.setattr(app, "estimar_precio_producto", pricing)
    monkeypatch.setattr(app, "estimar_etiquetas_producto", MagicMock(side_effect=AssertionError("Extra paid call")))
    output = app.modulo_extraer_textos(np.zeros((32,32,3), dtype=np.uint8), None, "ramen", None)
    assert len(output) == 14 and output[12] == "ramen" and output[5] == 20
    prompt = sdk.models.generate_content.call_args.kwargs["contents"][-1]
    assert "2 o 3 párrafos" in prompt and "Sin títulos, viñetas" in prompt
    assert sdk.models.generate_content.call_count == pricing.call_count == 1
    assert "test_" not in output[13][0]


def test_oauth_one_use_and_pkce(monkeypatch):
    from urllib.parse import urlsplit, parse_qs
    oauth_guard.issue_oauth("state", "verifier")
    with pytest.raises(ValueError):
        oauth_guard.consume_oauth("state", "attacker")
    assert oauth_guard.consume_oauth("state", "state") == "verifier"
    with pytest.raises(ValueError):
        oauth_guard.consume_oauth("state", "state")
    result = app.login()
    query = parse_qs(urlsplit(result.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    monkeypatch.setenv("APP_ALLOWED_EMAILS", "allowed@example.com")
    assert oauth_guard.email_allowed("allowed@example.com")
    assert not oauth_guard.email_allowed("stranger@example.com")


def test_visual_variants_uses_inline_image_and_grounded_search(monkeypatch):
    import numpy as np
    session = {"gemini_key": "key"}
    monkeypatch.setattr(app, "_validar_sesion", lambda request: (session, None))
    result = response({"producto_identificado": "Pocky", "marca_identificada": "Glico",
                       "tiene_variantes": True,
                       "variantes": [{"gramaje": "40G", "fuente": "https://example.com", "precio_aprox": 30}],
                       "justificacion": "Otra presentación"})
    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs)
        return result

    # No Files API: reproduces the actual gateway interface instead of accepting arbitrary attributes.
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    monkeypatch.setattr(app, "GeminiClient", lambda **kwargs: client)
    recommendation, report, kind = app.buscar_variantes_por_imagen(
        np.zeros((32, 32, 3), dtype=np.uint8), "Pocky", "Glico", None)
    assert kind == "Variable"
    assert "✅" in recommendation and "40G" in report
    assert len(calls) == 1
    assert calls[0]["contents"][0].inline_data.mime_type == "image/jpeg"
    assert calls[0]["contents"][0].inline_data.data.startswith(b"\xff\xd8")
    assert calls[0]["config"].tools


def test_watermark_uses_bundled_logo_without_drive(monkeypatch, tmp_path):
    from PIL import Image
    path = tmp_path / "product.jpg"
    Image.new("RGB", (1024, 1024), "white").save(path)
    app.estampar_logo(str(path), None, None)
    with Image.open(path) as result:
        assert result.format == "JPEG"
        assert min(result.crop((256,256,768,768)).convert("L").getextrema()) < 250
        assert min(result.crop((800,800,1000,1000)).convert("L").getextrema()) < 100
    # A failed Drive logo download still uses the official bundled asset.
    app.estampar_logo(str(path), None, "unavailable-logo")


def test_generation_always_brands_after_qa(monkeypatch, tmp_path):
    import io
    from PIL import Image
    candidate = Image.new("RGB", (1024, 1024), "red")
    buffer = io.BytesIO()
    candidate.save(buffer, format="PNG")
    reference = str(tmp_path / "reference.png")
    candidate.save(reference)
    client = MagicMock()
    monkeypatch.setattr(app, "GeminiClient", lambda **kwargs: client)
    monkeypatch.setattr(app, "_extraer_imagen_bytes", lambda result: buffer.getvalue())
    monkeypatch.setattr(app, "_imagen_para_ia", lambda path: "reference")
    monkeypatch.setattr(app, "_validacion_local_imagen", lambda path: [])
    monkeypatch.setattr(app, "_validar_con_vision", lambda *args: {"aprobada": True, "puntuacion": 99})
    stamp = MagicMock()
    monkeypatch.setattr(app, "estampar_logo", stamp)
    path = str(tmp_path / "out.jpg")
    result = app.generar_foto_individual("scene", reference, path, "key", None, None, slot="1_hd")
    assert result["ruta"] == path
    stamp.assert_called_once_with(path, None, None)
    stamp.side_effect = OSError("missing logo")
    result = app.generar_foto_individual("scene", reference, path, "key", None, None, slot="1_hd")
    assert result["ruta"] is None and "marca de agua" in result["resumen"]
    assert not os.path.exists(path)
