"""Inventory extraction, exact SKU matching and confirmed visible publication.

HTTP doubles only: no store writes, Google calls or paid generation.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import select

from catalog_platform.database import transaction
from catalog_platform.models import Product
from catalog_platform.woocommerce_compare import compare, read_store, remote_row
from catalog_platform.woocommerce_export import Exporter
from test_catalog_platform import setup, create, ORIGIN
from test_woocommerce_colab import store, source, options
from test_woocommerce_api import publication, submit
from catalog_platform import worker


def local(sku, **overrides):
    return {"sku": sku, "name": sku, "stock": 4, "kind": "simple", "parent_sku": "",
        "brand": "", "category": "", **overrides}


def remote(sku, **overrides):
    return remote_row({"id": 100, "sku": sku, "name": sku, "type": "simple", "status": "publish",
        "catalog_visibility": "visible", "manage_stock": True, "stock_quantity": 4, **overrides})


def test_comparison_preserves_all_states_unknowns_and_exact_skus():
    locals = [local(sku) for sku in ["OK", "DRAFT", "HIDDEN", "MISSING", "DIFF", "UNKNOWN", "DUP", "TYPE", "case"]]
    remotes = [remote("OK"), remote("DRAFT", status="draft"), remote("HIDDEN", catalog_visibility="hidden"),
        remote("DIFF", stock_quantity=0), remote("UNKNOWN", manage_stock=False, stock_quantity=0),
        remote("DUP"), remote("DUP", id=101), remote("TYPE", type="variable"), remote("CASE"), remote("")]
    result = compare(locals, remotes)
    rows = {row["sku"]: row for row in result["rows"]}
    assert rows["OK"]["publication"] == "published" and rows["OK"]["stock_comparison"] == "same"
    assert rows["DRAFT"]["publication"] == "draft"
    assert rows["HIDDEN"]["publication"] == "hidden"
    assert rows["MISSING"]["publication"] == rows["case"]["publication"] == "missing_woocommerce"
    assert rows["CASE"]["publication"] == "missing_app"
    assert rows["DIFF"]["difference"] == -4 and rows["DIFF"]["stock_comparison"] == "different"
    assert rows["UNKNOWN"]["woocommerce"]["stock"] is None and rows["UNKNOWN"]["difference"] is None
    assert rows["DUP"]["publication"] == rows["TYPE"]["publication"] == "conflict"
    assert rows[""]["publication"] == "no_sku"
    assert result["summary"]["stock_different"] == 1


def test_variations_inherit_parent_publication_and_shared_stock_is_not_double_counted():
    parent = {"id": 1, "sku": "F", "status": "draft", "manage_stock": True, "stock_quantity": 12}
    variation = remote_row({"id": 2, "sku": "V", "status": "publish", "manage_stock": "parent"}, parent)
    result = compare([local("V", kind="variant", parent_sku="F")], [variation])["rows"][0]
    assert result["publication"] == "draft" and result["woocommerce"]["stock"] == 12
    assert result["difference"] is None
    variation["parent_sku"] = "WRONG"
    assert compare([local("V", kind="variant", parent_sku="F")], [variation])["rows"][0]["publication"] == "conflict"
    assert compare([local("F", kind="family")], [remote("F", type="variable")])["rows"][0]["stock_comparison"] == "not_applicable"


@pytest.mark.parametrize("with_headers", [True, False])
def test_extraction_reads_product_and_variation_pagination(store, monkeypatch, with_headers):
    calls = []
    def request(session, method, url, **kwargs):
        assert method.upper() == "GET" and session.headers["User-Agent"] == "RinconDeAsia-CatalogExporter/1.0"
        params = kwargs["params"]
        calls.append((url.rsplit("/", 1)[-1], params["page"]))
        if url.endswith("/products"):
            items = [{"id": n, "sku": f"P{n}", "type": "variable" if n == 1 else "simple", "status": "publish"}
                     for n in range(1, 102)]
        else:
            items = [{"id": 1000 + n, "sku": f"V{n}", "status": "publish"} for n in range(101)]
        start = (params["page"] - 1) * 100
        return SimpleNamespace(ok=True, status_code=200, json=lambda: items[start:start + 100],
            headers={"X-WP-TotalPages": "2"} if with_headers else {})
    monkeypatch.setattr(requests.Session, "request", request)
    engine = Exporter()
    try:
        snapshot = read_store(engine)
        assert snapshot["products"] == 101 and snapshot["variations"] == 101
        assert ("products", 2) in calls and ("variations", 2) in calls
    finally:
        engine.close()


@pytest.mark.parametrize("failure", ["repeat", "http", "invalid"])
def test_failed_or_repeated_page_never_returns_a_partial_comparison(store, monkeypatch, failure):
    def request(session, method, url, **kwargs):
        page = kwargs["params"]["page"]
        if page == 2 and failure == "http":
            raise requests.Timeout("controlled timeout")
        items = [{"id": 1, "sku": "P", "status": "publish"}]
        if failure == "invalid":
            items = {"message": "error"}
        return SimpleNamespace(ok=True, status_code=200, json=lambda: items, headers={"X-WP-TotalPages": "2"})
    monkeypatch.setattr(requests.Session, "request", request)
    engine = Exporter()
    try:
        with pytest.raises((ValueError, requests.Timeout)):
            read_store(engine)
    finally:
        engine.close()


def test_comparison_endpoint_is_tenant_scoped_and_does_not_modify_stock_or_status(publication):
    client, value, (calls, products, *_) = publication
    create(client, sku="S1", stock=9)
    products["S1"] = {"id": 11, "sku": "S1", "name": "Ramen", "status": "publish", "type": "simple",
        "manage_stock": True, "stock_quantity": 4}
    response = client.get("/api/woocommerce/inventory-comparison?refresh=true")
    assert response.status_code == 200, response.text
    row = response.json()["rows"][0]
    assert row["publication"] == "published" and row["difference"] == -5
    assert all(call["method"] == "GET" for call in calls)
    with transaction() as db:
        product = db.scalar(select(Product).where(Product.tenant_id == value["platform_tenant"], Product.sku == "S1"))
        assert product.stock == 9 and product.status == "pending"
    value["platform_tenant"] = "other-store"
    assert client.get("/api/woocommerce/inventory-comparison").json()["rows"][0]["publication"] == "missing_app"
    client.cookies.clear()
    assert client.get("/api/woocommerce/inventory-comparison").status_code == 401


def test_new_and_existing_drafts_are_published_visible_without_duplicate_creation(store):
    calls, products, *_ = store
    engine = Exporter(source(), write=True)
    try:
        engine.execute("simple", "S1", options())
        before = deepcopy(products["S1"])
        engine.execute("simple", "S1", {**options(), "status": "publish"})
        assert products["S1"] == {**before, "status": "publish", "catalog_visibility": "visible"}
        assert len([c for c in calls if c["method"] == "POST" and c["endpoint"] == "wc/v3/products"]) == 1
        assert any(e["action"] == "producto_publicado" for e in engine.events)
    finally:
        engine.close()


def test_family_is_only_published_after_all_selected_variations_finish(store, monkeypatch):
    calls, products, variations, _ = store
    engine = Exporter(source(), write=True)
    original = engine.ns["wc"]
    def fail_second(method, endpoint, data=None, params=None):
        if method == "POST" and endpoint.endswith("/variations") and data["sku"] == "V2":
            raise ValueError("Controlled variation failure")
        return original(method, endpoint, data=data, params=params)
    engine.ns["wc"] = fail_second
    try:
        with pytest.raises(ValueError, match="Controlled"):
            engine.execute("family", "FAMILIA", {**options(), "status": "publish"})
        assert products["FAMILIA"]["status"] == "draft" and set(variations) == {"V1"}
        assert not any(c["method"] == "PUT" for c in calls)
        engine.ns["wc"] = original
        engine.execute("family", "FAMILIA", {**options(), "status": "publish"})
        assert products["FAMILIA"]["status"] == "publish" and set(variations) == {"V1", "V2"}
        assert calls[-1]["method"] == "PUT"
        engine.execute("family", "FAMILIA", {**options(), "status": "publish"})
        assert len([c for c in calls if c["method"] == "PUT"]) == 1
    finally:
        engine.close()


def test_api_default_is_publish_and_explicit_draft_remains_supported(publication):
    client, _, (_, products, *_) = publication
    body = {"selection": {"kind": "simple", "sku": "S1"}, "options": {"images": False}}
    response = client.post("/api/woocommerce/preview", json=body, headers=ORIGIN)
    assert response.json()["preview"]["new_status"] == "publish"
    body["options"]["status"] = "draft"
    review = client.post("/api/woocommerce/preview", json=body, headers=ORIGIN).json()
    assert review["preview"]["new_status"] == "draft"
    accepted = submit(client, review).json()["job"]
    worker.execute_job(accepted["id"])
    assert products["S1"]["status"] == "draft"
    body["options"]["status"] = "publish"
    review = client.post("/api/woocommerce/preview", json=body, headers=ORIGIN).json()
    accepted = submit(client, review).json()["job"]
    worker.execute_job(accepted["id"])
    assert products["S1"]["status"] == "publish"


def test_published_family_still_requires_specific_permission_to_add_variations(publication):
    client, _, (_, products, *_) = publication
    products["FAMILIA"] = {"id": 1, "sku": "FAMILIA", "type": "variable", "status": "publish"}
    response = client.post("/api/woocommerce/preview", json={"selection": {"kind": "family", "sku": "FAMILIA"},
        "options": {"images": False}}, headers=ORIGIN)
    assert response.status_code == 422 and "Autoriza" in response.json()["detail"]


def test_simple_sku_cannot_publish_an_existing_variable_product(store):
    calls, products, *_ = store
    products["S1"] = {"id": 15, "sku": "S1", "type": "variable", "status": "draft"}
    engine = Exporter(source(), write=True)
    try:
        with pytest.raises(ValueError, match="otro tipo"):
            engine.execute("simple", "S1", {**options(), "status": "publish"})
        assert all(call["method"] == "GET" for call in calls)
    finally:
        engine.close()


def test_failed_comparison_endpoint_does_not_return_old_snapshot_as_fresh(publication, monkeypatch):
    from catalog_platform import woocommerce_api
    client, _, _ = publication
    first = client.get("/api/woocommerce/inventory-comparison")
    assert first.status_code == 200
    def fail(_):
        raise ValueError("No se pudo leer el catálogo completo.")
    monkeypatch.setattr(woocommerce_api, "read_store", fail)
    result = client.get("/api/woocommerce/inventory-comparison?refresh=true")
    assert result.status_code == 502 and "rows" not in result.json()
