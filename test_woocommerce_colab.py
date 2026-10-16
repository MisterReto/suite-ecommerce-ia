"""Accepted Colab behavior, using controlled HTTP/Google doubles and zero store writes."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from catalog_platform.woocommerce_export import Exporter, CORE, StoreSession, safe_error


def test_woocommerce_image_index_only_reads_direct_generated_images():
    from catalog_platform.woocommerce_export import index_images
    from test_sheet_catalog_sync import DriveDouble
    sdk = DriveDouble("catalog")
    sdk.items["own"]["name"] = "S1_1_hd.jpg"
    sdk.items["shared"]["name"] = "S1_2_uso.jpg"
    sdk.items["root-copy"] = {"id": "root-copy", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": ["catalog"]}
    sdk.items["subfolder"] = {"id": "subfolder", "name": "backup", "mimeType": "application/vnd.google-apps.folder", "parents": ["generated"]}
    sdk.items["nested-copy"] = {"id": "nested-copy", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": ["subfolder"]}
    assert {item["id"] for item in index_images(sdk, "generated")} == {"own", "shared"}
    with pytest.raises(ValueError, match="debe ser imagenes_generadas"):
        index_images(sdk, "subfolder")


def source():
    simple = {"sku": "S1", "tipo": "simple", "nombre_producto": "Ramen", "Marca": "Marca original",
        "precio": "$35.00", "Precio descuento": "$30.00", "Existencias": "4",
        "categorias": "Ramen > Sopa", "etiquetas": "Japón, Comida", "descripcion_corta": "Resumen",
        "descripcion_larga": "Descripción original", "imagenes": "OTRO_SKU_1.png"}
    parent = {**simple, "sku": "FAMILIA", "tipo": "variable", "nombre_producto": "Familia"}
    children = {sku: {**simple, "sku": sku, "tipo": "variation", "sku_padre": "FAMILIA"}
                for sku in ("V1", "V2")}
    return {"SIMPLES": {"S1": simple}, "PADRES": {"FAMILIA": parent}, "VARIANTES": children,
        "COMPLETA": {"S1": {"codigo_barras": "123456789012"},
                     "V1": {"atributo_nombre": "Sabor", "atributo_valor": "Chocolate"},
                     "V2": {"atributo_nombre": "Sabor", "atributo_valor": "Fresa"}},
        "CSV_VARIANTES": {}, "ARCHIVOS": [
            {"id": "wrong", "name": "OTRO_SKU_1.png", "mimeType": "image/png"},
            {"id": "legacy", "name": "S1_1.png", "mimeType": "image/png"},
            {"id": "real", "name": "S1_1_hd.jpg", "mimeType": "image/jpeg"}], "MEDIA_SYNC": {}}


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("WOOCOMMERCE_URL", "https://rincon.creandotusite.com")
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_KEY", "test-read-write-key")
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_SECRET", "test-read-write-secret")
    monkeypatch.setenv("WP_USERNAME", "test-wordpress-user")
    monkeypatch.setenv("WP_APP_PASSWORD", "test-wordpress-password")
    calls, products, variations = [], {}, {}
    media = {22: "S1_1_hd.jpg"}

    def request(session, method, url, **kwargs):
        assert session.headers["Accept"] == "application/json"
        assert session.headers["User-Agent"] == "RinconDeAsia-CatalogExporter/1.0"
        assert kwargs["allow_redirects"] is False
        method = method.upper()
        endpoint = url.split("/wp-json/", 1)[1]
        body = kwargs.get("json") or {}
        calls.append({"method": method, "endpoint": endpoint, "body": deepcopy(body), "data": kwargs.get("data"), "params": deepcopy(kwargs.get("params") or {})})
        if endpoint == "wc/v3/products" and method == "GET":
            params = kwargs.get("params") or {}
            sku = params.get("sku")
            result = [p for code, p in products.items() if (not sku or code == sku)
                and ((p.get("status") == "trash") == (params.get("status") == "trash"))]
            size, page = params.get("per_page", 100), params.get("page", 1)
            result = result[(page - 1) * size:page * size]
        elif endpoint == "wc/v3/products" and method == "POST":
            assert body["sku"] not in products, "No duplicate product write"
            result = {**deepcopy(body), "id": 100 + len(products)}
            products[body["sku"]] = result
        elif endpoint.endswith("/variations") and method == "GET":
            result = [v for v in variations.values() if (v.get("status") == "trash") == ((kwargs.get("params") or {}).get("status") == "trash")]
        elif endpoint.endswith("/variations") and method == "POST":
            assert body["sku"] not in variations
            result = {**deepcopy(body), "id": 200 + len(variations)}
            variations[body["sku"]] = result
        elif endpoint.startswith("wc/v3/products/"):
            existing = next((p for p in products.values() if str(p["id"]) == endpoint.rsplit("/", 1)[-1]), None)
            if method == "PUT" and existing:
                existing.update(deepcopy(body))
                result = existing
            else:
                result = [] if method == "GET" else {**body, "id": len(calls)}
        elif endpoint.startswith("wp/v2/media/"):
            result = {"id": 22, "source_url": "https://rincon.creandotusite.com/uploads/" + media[22]}
        elif endpoint == "wp/v2/media":
            assert session.auth == ("test-wordpress-user", "test-wordpress-password")
            assert kwargs["data"] == b"controlled-image"
            result = {"id": 33, "source_url": "https://rincon.creandotusite.com/uploads/S1_1_hd.jpg"}
        else:
            raise AssertionError(endpoint)
        return SimpleNamespace(ok=True, status_code=201 if method == "POST" else 200,
                               json=lambda: deepcopy(result), text=json.dumps(result), headers={})

    monkeypatch.setattr(requests.Session, "request", request)
    return calls, products, variations, media


def options(images=False, stock=False, tags=False):
    return {"images": images, "stock": stock, "tags": tags, "allow_published_family": False}


def test_originals_and_raw_images_are_excluded_from_old_job_snapshots(store):
    data = source()
    data["ARCHIVOS"] += [{"id": str(i), "name": name, "mimeType": "image/jpeg"} for i, name in enumerate([
        "S1_2_uso_raw.jpg", "S1_3_original.jpg", "S1_referencia_frente.jpg", "S1_4_raw.jpg", "S1_1_hd_backup.jpg"])]
    engine = Exporter(source=data)
    try:
        preview = engine.preview("simple", "S1", options(images=True))
        assert preview["items"][0]["images"] == [{"id": "real", "name": "S1_1_hd.jpg"}]
        assert {item["id"] for item in engine.snapshot("simple", "S1")["ARCHIVOS"]} == {"real"}
    finally:
        engine.close()


def test_trashed_sku_is_detected_before_media_or_product_writes(store):
    calls, products, *_ = store
    products["S1"] = {"id": 8772, "sku": "S1", "status": "trash", "type": "simple"}
    engine = Exporter(source(), write=True)
    try:
        for operation in (lambda: engine.preflight("simple", "S1"),
                          lambda: engine.execute("simple", "S1", options())):
            with pytest.raises(ValueError, match="SKU S1.*papelera") as caught:
                operation()
            assert "8772" not in str(caught.value)
        assert calls and all(c["method"] == "GET" for c in calls)
        assert any(c["params"].get("status") == "trash" for c in calls)
    finally:
        engine.close()


def test_trashed_variation_is_detected_without_recreating_it(store):
    calls, products, variations, _ = store
    engine = Exporter(source(), write=True)
    try:
        engine.execute("family", "FAMILIA", options())
        variations["V1"]["status"] = "trash"
        calls.clear()
        with pytest.raises(ValueError, match="V1.*papelera"):
            engine.preflight("variant", "V1")
        assert all(c["method"] == "GET" for c in calls)
    finally:
        engine.close()


def test_store_errors_use_the_json_message_without_encoded_response_body(store, monkeypatch):
    response = SimpleNamespace(ok=False, status_code=400,
        json=lambda: {"code": "test", "message": "Error &quot;SKU&quot; test-read-write-secret"})
    monkeypatch.setattr(requests.Session, "request", lambda *a, **kw: response)
    engine = Exporter(source(), write=True)
    try:
        with pytest.raises(ValueError) as error:
            engine.ns["wc"]("POST", "products", data={"sku": "S1"})
        assert 'HTTP 400. Error "SKU"' in str(error.value)
        assert "test-read-write-secret" not in safe_error(error.value)
    finally:
        engine.close()


def test_all_twenty_seven_colab_functions_remain_exactly_unchanged():
    manifest = json.loads((CORE.parents[1] / "tests/fixtures/woocommerce_colab_manifest.json").read_text())
    text = CORE.read_text(encoding="utf8")
    actual = {node.name: hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest()
              for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)}
    assert actual == manifest["functions"] and len(actual) == 27


def test_single_product_preserves_values_and_remains_draft(store):
    calls, products, *_ = store
    engine = Exporter(source(), write=True)
    try:
        events = engine.execute("simple", "S1", options(stock=True, tags=True))
        created = products["S1"]
        assert created["status"] == "draft" and created["catalog_visibility"] == "hidden"
        assert created["name"] == "Ramen" and created["description"] == "Descripción original"
        assert created["regular_price"] == "35.00" and created["sale_price"] == "30.00"
        assert created["manage_stock"] and created["stock_quantity"] == 4
        assert created["attributes"][0]["options"] == ["Marca original"]
        assert created["meta_data"][0]["value"] == "123456789012"
        assert created["categories"] and created["tags"]
        assert any(event["action"] == "producto_creado" for event in events)
        engine.execute("simple", "S1", options())
        assert len([call for call in calls if call["method"] == "POST" and call["endpoint"] == "wc/v3/products"]) == 1
    finally:
        engine.close()


def test_family_and_individual_variant_reuse_parent_without_duplicates(store):
    _, products, variations, _ = store
    engine = Exporter(source(), write=True)
    try:
        engine.execute("variant", "V1", options())
        assert set(products) == {"FAMILIA"} and set(variations) == {"V1"}
        assert products["FAMILIA"]["type"] == "variable" and products["FAMILIA"]["status"] == "draft"
        assert products["FAMILIA"]["attributes"][0]["options"] == ["Chocolate", "Fresa"]
        engine.execute("family", "FAMILIA", options(stock=True))
        assert len(products) == 1 and set(variations) == {"V1", "V2"}
        assert variations["V2"]["stock_quantity"] == 4
    finally:
        engine.close()


def test_published_parent_requires_specific_authorization_before_any_write(store):
    calls, products, *_ = store
    products["FAMILIA"] = {"sku": "FAMILIA", "id": 10, "type": "variable", "status": "publish", "attributes": []}
    engine = Exporter(source(), write=True)
    try:
        with pytest.raises(ValueError, match="ya está publicada"):
            engine.execute("variant", "V1", options())
        assert not any(call["method"] == "POST" for call in calls)
    finally:
        engine.close()


def test_preview_resolves_real_sku_images_and_performs_no_store_writes(store):
    calls, *_ = store
    engine = Exporter(source())
    try:
        preview = engine.preview("simple", "S1", options(images=True))
        assert preview["items"][0]["images"] == [{"id": "real", "name": "S1_1_hd.jpg"}]
        assert not calls
        with pytest.raises(ValueError, match="no puede escribir"):
            engine.ns["datos_base"](engine.ns["SIMPLES"]["S1"], "simple", False, False)
    finally:
        engine.close()


def test_existing_media_is_validated_and_reused_without_upload(store):
    calls, products, *_ = store
    engine = Exporter(source(), write=True, media_cache={"https://rincon.creandotusite.com|real": 22})
    try:
        engine.execute("simple", "S1", options(images=True))
        assert products["S1"]["images"] == [{"id": 22}]
        assert not any(call["endpoint"] == "wp/v2/media" for call in calls)
    finally:
        engine.close()


def test_wrong_cached_media_is_replaced_with_real_drive_image(store):
    calls, products, _, media = store
    media[22] = "OTRO_SKU_1.png"
    engine = Exporter(source(), drive=SimpleNamespace(files=lambda: SimpleNamespace(get_media=lambda **kw: kw)),
                      write=True, media_cache={"https://rincon.creandotusite.com|real": 22})
    class Downloader:
        def __init__(self, stream, request):
            assert request["fileId"] == "real"
            self.stream = stream
        def next_chunk(self):
            self.stream.write(b"controlled-image")
            return None, True
    engine.ns["MediaIoBaseDownload"] = Downloader
    try:
        engine.execute("simple", "S1", options(images=True))
        assert products["S1"]["images"] == [{"id": 33}]
        assert len([call for call in calls if call["endpoint"] == "wp/v2/media"]) == 1
    finally:
        engine.close()


def test_http_406_and_errors_do_not_expose_credentials(store):
    engine = Exporter(source())
    try:
        with pytest.raises(RuntimeError, match="ModSecurity"):
            engine.ns["comprobar_respuesta"](SimpleNamespace(status_code=406), "Consultar productos")
        assert "test-read-write-secret" not in safe_error(RuntimeError("test-read-write-secret"))
    finally:
        engine.close()
