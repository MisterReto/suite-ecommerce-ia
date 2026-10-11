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
    monkeypatch.setenv("SUITE_SERVICE_ROLE", "sync")
    monkeypatch.setenv("SUITE_DRIVE_ONLY", "false")
    monkeypatch.setattr(native_tools, "worker_enabled", lambda: False)
    monkeypatch.setitem(native_tools.runtime.SESSIONS, "native-test", {"email": "test@example.test", "role": "admin"})
    app = FastAPI()
    native_tools.register(app)
    with TestClient(app, cookies={"session_id": "native-test"}) as value:
        yield value


def test_confirmation_role_method_and_store_gates_prevent_writes(client, monkeypatch):
    handler = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(native_tools.inventory_web, "inventory_count_bulk", handler)
    assert client.post("/api/tools/counts", json={"counts": []}).status_code == 422
    assert client.post("/api/tools/counts", json={"confirm": 1}).status_code == 422
    assert client.post("/api/tools/counts", content="malformed").status_code == 422
    assert client.get("/api/tools/counts").status_code == 405
    assert client.post("/api/tools/not-allowed", json={"confirm": True}).status_code == 404
    native_tools.runtime.SESSIONS["native-test"]["role"] = "viewer"
    assert client.post("/api/tools/counts", json={"confirm": True}).status_code == 403
    native_tools.runtime.SESSIONS["native-test"]["role"] = "editor"
    assert client.post("/api/tools/batch-step", json={"confirm": True}).status_code == 403
    native_tools.runtime.SESSIONS["native-test"]["role"] = "admin"
    monkeypatch.setenv("SUITE_DRIVE_ONLY", "true")
    assert client.post("/api/tools/batch-create", json={"confirm": True}).status_code == 503
    handler.assert_not_called()


def test_counts_delegate_the_exact_existing_payload_after_confirmation(client, monkeypatch):
    payload = {"confirm": True, "counts": [{"sku": "1234567890123", "stock": 7}]}
    async def established(request):
        assert await request.json() == payload
        return {"ok": True, "message": "Guardado"}
    handler = AsyncMock(side_effect=established)
    monkeypatch.setattr(native_tools.inventory_web, "inventory_count_bulk", handler)
    assert client.post("/api/tools/counts", json=payload).json()["message"] == "Guardado"
    handler.assert_awaited_once()


def test_read_viewer_and_session_contract(client, monkeypatch):
    monkeypatch.setattr(native_tools, "inventory", lambda value, q: {"ok": True, "rows": [], "query": q})
    native_tools.runtime.SESSIONS["native-test"]["role"] = "viewer"
    assert client.get("/api/tools/inventory?q=123").json()["query"] == "123"
    client.cookies.clear()
    assert client.get("/api/tools/inventory").status_code == 401


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


def test_signed_forwarder_is_used_without_replacing_the_session(client, monkeypatch):
    monkeypatch.setattr(native_tools, "worker_enabled", lambda: True)
    forwarded = AsyncMock(return_value={"ok": True, "summary": {}})
    monkeypatch.setattr(native_tools, "forward_tool", forwarded)
    assert client.get("/api/tools/review").status_code == 200
    forwarded.assert_awaited_once()
    request, runtime = forwarded.call_args.args
    assert request.url.path == "/api/tools/review"
    assert runtime is native_tools.runtime


def test_retired_origins_redirect_without_oauth_or_old_ui():
    with TestClient(retired_service.app, follow_redirects=False) as client:
        for path, destination in [("/", "/#home"), ("/inventory-hub", "/#inventory/count"),
                                  ("/woocommerce-batch-sync", "/#more/publication"),
                                  ("/auth/callback?code=never-forward&state=old", "/login")]:
            result = client.get(path)
            assert result.status_code == 303
            assert result.headers["location"] == retired_service.PUBLIC_ORIGIN + destination
            assert "no-store" in result.headers["cache-control"]
            assert "gradio" not in result.text.casefold()
            assert "set-cookie" not in result.headers
        assert client.post("/image-sync-one", json={"sku": "A"}).status_code == 410
        assert client.get("/service-health").json()["gradio"] is False
