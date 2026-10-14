"""Regression boundaries for the local-only application; no live provider calls."""
import ast
from pathlib import Path
from unittest.mock import Mock
import pytest
from sqlalchemy import select
from test_catalog_platform import setup, create, ORIGIN
from catalog_platform import worker
from catalog_platform.database import transaction
from catalog_platform.models import Product, GenerationJob, uid
from drive_image_index import resolve_product_images

ROOT = Path(__file__).parent
RETIRED_KINDS = ("publication", "stock_sync", "ecommerce_pull", "webhook", "loyverse_sync")
RETIRED_PATHS = (
    "/api/platform/ecommerce/refresh", "/api/platform/import/woocommerce",
    "/api/webhooks/woocommerce", "/api/webhooks/loyverse",
    "/webhooks/woocommerce", "/webhooks/loyverse",
    "/loyverse/connect", "/api/tools/media-sync", "/api/tools/batch-create",
)

@pytest.mark.parametrize("path", RETIRED_PATHS)
def test_removed_endpoints_do_not_accept_operations(setup, path):
    client, _, _ = setup
    response = client.post(path, json={"confirm": True, "request_key": uid()}, headers=ORIGIN)
    assert response.status_code == 404, response.text

def test_only_active_connections_are_visible(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setenv("WC_WRITE_ENABLED", "true")
    monkeypatch.setenv("WP_MEDIA_WRITE_ENABLED", "true")
    response = client.get("/api/platform/connections")
    assert [row["name"] for row in response.json()["items"]] == ["Google Drive", "Google Sheets", "IA · Gemini"]
    assert "private-token" not in response.text

@pytest.mark.parametrize("kind", RETIRED_KINDS)
def test_old_job_kind_fails_before_loading_credentials_or_using_drive(kind, monkeypatch):
    credentials = Mock(side_effect=AssertionError("Credentials must not be loaded"))
    monkeypatch.setattr(worker, "load", credentials)
    with pytest.raises(ValueError, match="retirado"):
        worker.process({"kind": kind})
    credentials.assert_not_called()

@pytest.mark.parametrize("kind", RETIRED_KINDS)
def test_old_job_retry_is_rejected_and_history_preserved(setup, kind):
    client, value, _ = setup
    with transaction() as db:
        job = GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"],
                            kind=kind, status="failed", request_key=uid())
        db.add(job); db.flush(); job_id = job.id
    response = client.post("/api/platform/jobs/" + job_id + "/retry",
                           json={"confirm": True, "request_key": uid()}, headers=ORIGIN)
    assert response.status_code == 410, response.text
    with transaction() as db:
        assert db.get(GenerationJob, job_id).status == "failed"

def test_store_metadata_is_historical_and_local_stock_remains_editable(setup, monkeypatch):
    client, _, _ = setup
    product = create(client, stock=3)
    with transaction() as db:
        row = db.get(Product, product["id"])
        row.woocommerce_product_id = 42
        row.loyverse_item_id = "historical-item"
        row.woocommerce_stock = 77
    monkeypatch.setenv("STOCK_AUTHORITY", "loyverse")
    response = client.post("/api/platform/products/" + product["id"] + "/stock",
                           json={"quantity": 5, "event_id": uid(), "version": product["version"],
                                 "reason": "Conteo local"}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    visible = client.get("/api/platform/products/" + product["id"]).json()["product"]
    assert not any(key.startswith(("woocommerce_", "loyverse_")) for key in visible)
    with transaction() as db:
        row = db.get(Product, product["id"])
        assert row.stock == 5 and row.woocommerce_stock == 77
        assert row.woocommerce_product_id == 42 and row.loyverse_item_id == "historical-item"

def test_drive_legacy_naming_keeps_exact_and_canonical_matches():
    index = {"sku_1_hd.jpg": {"id": "a"}, "sku_2_uso.jpg": {"id": "b"},
             "sku_3_comercial.jpg": {"id": "c"}}
    refs = resolve_product_images({"sku": "SKU", "imagenes": "SKU_1.png,SKU_2.png,SKU_3.png"}, index)
    assert [row["drive_file"]["id"] for row in refs] == ["a", "b", "c"]
    assert [row["resolved_filename"] for row in refs] == ["SKU_1_hd.jpg", "SKU_2_uso.jpg", "SKU_3_comercial.jpg"]
    assert all(row["resolution"] == "fallback" for row in refs)

def test_frontend_has_no_external_store_controls_and_keeps_capture_flow():
    for name in ("frontend/app/page.tsx", "frontend/components/CaptureStudio.tsx",
                 "frontend/components/InventoryTools.tsx", "frontend/next.config.ts"):
        content = (ROOT / name).read_text(encoding="utf8").lower()
        assert "loyverse" not in content and "wordpress" not in content
        assert "/api/platform/ecommerce/" not in content
    capture = (ROOT / "frontend/components/CaptureStudio.tsx").read_text(encoding="utf8")
    for endpoint in ("/api/analyze", "/api/find-variants", "/api/family-cover",
                     "/api/generate", "/correct", "/api/save"):
        assert endpoint in capture

def test_runtime_has_no_import_of_removed_clients_or_bridge():
    removed = {"woocommerce_client", "loyverse_client", "ecommerce_services",
               "sync_bridge_protocol", "sync_gateway", "store_connection",
               "catalog_platform.ecommerce", "catalog_platform.webhooks", "catalog_platform.inventory"}
    for path in [*ROOT.glob("*.py"), *(ROOT / "catalog_platform").glob("*.py")]:
        if path.name.startswith("test"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
            if isinstance(node, ast.Import):
                assert not any(item.name in removed for item in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in removed

def test_archive_restore_preserves_family_stock_images_and_history(setup):
    client, _, drive = setup
    parent = create(client, sku="FAMILIAFULL", name="Familia", product_type="variable", price=None, stock=None)
    child = create(client, sku="CHILD1", parent_id=parent["id"], product_type="variation", stock=7,
                   attributes={"Tamaño": "41 g"})
    before = dict(drive.files)
    response = client.post("/api/platform/products/" + parent["id"] + "/archive",
                           json={"confirm": True, "version": parent["version"]}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 2
    assert client.get("/api/platform/products").json()["total"] == 0
    assert client.get("/api/platform/products?filter=archived").json()["total"] == 2
    result = client.post("/api/platform/products/" + parent["id"] + "/restore",
                         json={"confirm": True, "version": response.json()["product"]["version"]}, headers=ORIGIN)
    assert result.status_code == 200, result.text
    assert client.get("/api/platform/products").json()["total"] == 2
    assert client.get("/api/platform/products/" + child["id"]).json()["product"]["stock"] == 7
    assert drive.files == before

def test_archive_refuses_active_jobs_and_wrong_version(setup):
    client, value, _ = setup
    product = create(client)
    endpoint = "/api/platform/products/" + product["id"] + "/archive"
    assert client.post(endpoint, json={"confirm": True, "version": product["version"]+1}, headers=ORIGIN).status_code == 409
    with transaction() as db:
        db.add(GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"], product_id=product["id"],
                             kind="generation", status="queued", request_key=uid()))
    assert client.post(endpoint, json={"confirm": True, "version": product["version"]}, headers=ORIGIN).status_code == 409


def test_dashboard_and_logs_exclude_external_jobs(setup):
    client, value, _ = setup
    create(client)
    with transaction() as db:
        for kind, status in [("publication", "failed"), ("stock_sync", "queued"), ("generation", "failed")]:
            db.add(GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"],
                                 kind=kind, status=status, request_key=uid()))
    stats = client.get("/api/platform/dashboard").json()["stats"]
    assert stats["ai_errors"] == 1 and stats["pending_jobs"] == 0
    logs = client.get("/api/platform/events").json()["items"]
    assert logs and all(row["actor"] == value["email"] for row in logs)
    assert all("source" not in row and "destination" not in row for row in logs)
