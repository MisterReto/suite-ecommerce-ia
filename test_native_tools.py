"""Native tool contracts and retired public origins; all integrations are test doubles."""
import os
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "https://suite.example/auth/callback")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import native_tools
import retired_service


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(native_tools.runtime.SESSIONS, "native-test", {"email": "test@example.test", "role": "admin"})
    monkeypatch.setenv("APP_ROLE_MAP", '{"test@example.test":"admin"}')
    app = FastAPI()
    native_tools.register(app)
    with TestClient(app, cookies={"session_id": "native-test"}) as value:
        yield value


def test_confirmation_role_and_method_gates_prevent_writes(client, monkeypatch):
    handler = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(native_tools.sheet_inventory, "inventory_count_bulk", handler)
    assert client.post("/api/tools/counts", json={"counts": []}).status_code == 422
    assert client.post("/api/tools/counts", json={"confirm": 1}).status_code == 422
    assert client.post("/api/tools/counts", content="malformed").status_code == 422
    assert client.get("/api/tools/counts").status_code == 405
    assert client.post("/api/tools/not-allowed", json={"confirm": True}).status_code == 404
    native_tools.runtime.SESSIONS["native-test"]["role"] = "viewer"
    assert client.post("/api/tools/counts", json={"confirm": True}).status_code == 403
    native_tools.runtime.SESSIONS["native-test"]["role"] = "editor"
    assert client.post("/api/tools/batch-step", json={"confirm": True}).status_code == 404
    native_tools.runtime.SESSIONS["native-test"]["role"] = "admin"
    assert client.post("/api/tools/batch-create", json={"confirm": True}).status_code == 404
    handler.assert_not_called()


def test_counts_delegate_the_exact_existing_payload_after_confirmation(client, monkeypatch):
    payload = {"confirm": True, "counts": [{"sku": "1234567890123", "stock": 7}]}
    async def established(request):
        assert await request.json() == payload
        return {"ok": True, "message": "Guardado"}
    handler = AsyncMock(side_effect=established)
    monkeypatch.setattr(native_tools.sheet_inventory, "inventory_count_bulk", handler)
    assert client.post("/api/tools/counts", json=payload).json()["message"] == "Guardado"
    handler.assert_awaited_once()


def test_read_viewer_and_session_contract(client, monkeypatch):
    monkeypatch.setattr(native_tools, "inventory", lambda value, q: {"ok": True, "rows": [], "query": q})
    native_tools.runtime.SESSIONS["native-test"]["role"] = "viewer"
    assert client.get("/api/tools/inventory?q=123").json()["query"] == "123"
    client.cookies.clear()
    assert client.get("/api/tools/inventory").status_code == 401


def test_catalog_sync_requires_confirmation_and_editor_and_returns_verified_total(client, monkeypatch):
    from catalog_platform import sheet_sync
    sync = Mock(return_value={"updated": 2, "product_ids": ["parent", "child"]})
    monkeypatch.setattr(sheet_sync, "sync_inventory", sync)
    assert client.post("/api/tools/sync", json={"skus": ["CHILD"]}).status_code == 422
    native_tools.runtime.SESSIONS["native-test"]["role"] = "viewer"
    assert client.post("/api/tools/sync", json={"confirm": True, "skus": ["CHILD"]}).status_code == 403
    sync.assert_not_called()
    native_tools.runtime.SESSIONS["native-test"]["role"] = "editor"
    result = client.post("/api/tools/sync", json={"confirm": True, "skus": ["CHILD"]})
    assert result.status_code == 200 and result.json()["result"]["updated"] == 2
    assert sync.call_args.args[1] == ["CHILD"]


def test_sheet_mirror_failure_reports_saved_source_without_repeating_movement(monkeypatch):
    from catalog_platform import sheet_sync
    import sheet_inventory
    monkeypatch.setattr("catalog_platform.database.configured", lambda: True)
    sync = Mock(side_effect=RuntimeError("private-token"))
    monkeypatch.setattr(sheet_sync, "sync_inventory", sync)
    result = sheet_inventory.mirror_saved({"email": "test@example.test"}, ["A"])
    assert result["catalog_synced"] is False
    assert "No repitas el movimiento" in result["catalog_message"]
    assert "private-token" not in str(result)
    sync.assert_called_once()


def test_sync_api_exposes_partial_success_and_per_product_warnings(client, monkeypatch):
    from catalog_platform import sheet_sync
    expected = {"updated": 1, "failed": 1, "product_ids": ["good"],
                "warnings": [{"sku": "BAD", "name": "Producto inválido", "message": "Corrige las existencias."}]}
    monkeypatch.setattr(sheet_sync, "sync_inventory", Mock(return_value=expected))
    result = client.post("/api/tools/sync", json={"confirm": True, "skus": ["GOOD", "BAD"]})
    assert result.status_code == 200 and result.json()["ok"] is True
    assert result.json()["result"] == expected
    assert "1 producto no se pudo" in result.json()["message"] and "advertencias" in result.json()["message"]


def test_saved_counts_do_not_claim_complete_catalog_sync_after_partial_failure(monkeypatch):
    from catalog_platform import sheet_sync
    import sheet_inventory
    monkeypatch.setattr("catalog_platform.database.configured", lambda: True)
    monkeypatch.setattr(sheet_sync, "sync_inventory", Mock(return_value={"updated": 1, "failed": 1, "warnings": []}))
    result = sheet_inventory.mirror_saved({"email": "test@example.test"}, ["GOOD", "BAD"])
    assert result["catalog_synced"] is False and "No repitas el movimiento" in result["catalog_message"]


def test_native_sheet_write_uses_shared_capture_guard(monkeypatch):
    from contextlib import contextmanager
    import sheet_inventory
    events = []
    session = {"email": "test@example.test"}
    @contextmanager
    def guard(value):
        assert value is session
        events.append("lock")
        yield
        events.append("unlock")
    monkeypatch.setattr("catalog_platform.capture_bridge.sheet_write_guard", guard)
    def save(sheets, sheet, **kwargs):
        assert events == ["lock"] and kwargs == {"sku": "A"}
        events.append("write")
        return {"sku": "A"}
    assert sheet_inventory.write_inventory(session, save, object(), "sheet", sku="A") == {"sku": "A"}
    assert events == ["lock", "write", "unlock"]


def test_existing_history_is_read_without_creating_a_sheet(monkeypatch):
    sheets = Mock()
    sheets.spreadsheets().get().execute.return_value = {"sheets": []}
    assert native_tools.movements(sheets, "test-sheet") == []
    sheets.spreadsheets().values.assert_not_called()
    sheets.spreadsheets().batchUpdate.assert_not_called()
    sheets.spreadsheets().get().execute.return_value = {"sheets": [{"properties": {"title": native_tools.MOVEMENTS_SHEET}}]}
    sheets.spreadsheets().values().get().execute.return_value = {"values": [
        ["sku", "tipo", "stock_nuevo"], ["A", "Entrada", 2], ["B", "Salida", 1], ["A", "Ajuste", 3]]}
    assert [row["stock_nuevo"] for row in native_tools.movements(sheets, "test-sheet", "A")] == [3, 2]
    sheets.spreadsheets().batchUpdate.assert_not_called()




def test_retired_origins_redirect_without_oauth_or_old_ui():
    with TestClient(retired_service.app, follow_redirects=False) as client:
        for path, destination in [("/", "/#home"), ("/inventory-hub", "/#inventory/count"),
                                  ("/woocommerce-batch-sync", "/#home"),
                                  ("/auth/callback?code=never-forward&state=old", "/login")]:
            result = client.get(path)
            assert result.status_code == 303
            assert result.headers["location"] == retired_service.PUBLIC_ORIGIN + destination
            assert "no-store" in result.headers["cache-control"]
            assert "gradio" not in result.text.casefold()
            assert "set-cookie" not in result.headers
        assert client.post("/image-sync-one", json={"sku": "A"}).status_code == 410
        assert client.get("/service-health").json()["gradio"] is False
