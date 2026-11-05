"""Product removal for Google collaborators; no real Drive/Sheets mutations."""
import json
import logging
from unittest.mock import Mock

from googleapiclient.errors import HttpError
from httplib2 import Response
import pytest

from catalog_platform import sheet_sync
from catalog_platform.database import transaction
from catalog_platform.models import ProductImage
from drive_service import DriveService
from test_catalog_platform import setup, create, ORIGIN
from test_sheet_catalog_sync import DriveDouble, SheetDouble, response
import studio_api as studio


def denied(reason="insufficientFilePermissions"):
    return HttpError(Response({"status": 403}), json.dumps({"error": {
        "code": 403, "message": "private-token private-email@example.test",
        "errors": [{"reason": reason}]}}).encode(), uri="https://private.example/secret")


@pytest.fixture
def removal(setup, monkeypatch):
    client, value, _ = setup
    product = create(client)
    sdk = DriveDouble(value["platform_tenant"])
    sdk.close = Mock()
    sdk.items["own"]["capabilities"] = {"canTrash": False}
    writes = []
    original = sdk.update

    def update(fileId, body, **kwargs):
        if body.get("trashed") and fileId == "own":
            writes.append(fileId)
            return response(lambda: (_ for _ in ()).throw(denied()))
        return original(fileId, body, **kwargs)

    monkeypatch.setattr(sdk, "update", update)
    drive = DriveService(sdk, value["platform_tenant"])
    monkeypatch.setattr(drive, "working_folder", lambda *args: "backups")
    monkeypatch.setattr(sheet_sync, "DriveService", lambda *args: drive)
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (sdk, "sheet", [
        {"sku": product["sku"], "imagenes": "sprite.jpg"}]))
    sheets = SheetDouble([["sku", "imagenes"], [product["sku"], "sprite.jpg"]])
    sheets.close = Mock()
    monkeypatch.setattr(studio.runtime, "_get_sheets_service", lambda *args: sheets)
    with transaction() as db:
        db.add(ProductImage(tenant_id=value["platform_tenant"], product_id=product["id"], drive_file_id="own"))
    body = {"confirm": True, "version": product["version"], "delete_from_drive": True}
    return client, product, sdk, sheets, writes, body, value


def remove(case, **options):
    client, product, _, _, _, body, _ = case
    return client.request("DELETE", "/api/platform/products/" + product["id"],
                          json={**body, **options}, headers=ORIGIN)


def test_collaborator_can_remove_product_and_sheet_with_explicit_media_retention(removal):
    client, product, sdk, sheets, writes, _, _ = removal
    result = remove(removal, retain_untrashable_images=True)
    assert result.status_code == 200, result.text
    media = result.json()["drive"]
    assert media["retained_image_ids"] == ["own"] and media["trashed_image_ids"] == []
    assert media["sheet"]["deleted"] and media["backup_id"]
    assert sheets.rows == [["sku", "imagenes"]]
    assert not sdk.items["own"].get("trashed") and writes == []
    assert [item["mimeType"] for item in sdk.copies] == ["application/vnd.google-apps.spreadsheet"]
    assert client.get("/api/platform/products").json()["total"] == 0
    sdk.close.assert_called_once()
    sheets.close.assert_called_once()
    replay = remove(removal).json()
    assert replay["replayed"] and replay["drive"] == media
    assert len(sdk.copies) == 1, "A lost-response retry must not repeat external writes"


def test_strict_legacy_request_checks_all_permissions_before_backup_or_trash(removal, caplog):
    client, product, sdk, sheets, writes, _, _ = removal
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        result = remove(removal)
    assert result.status_code == 403 and "Google" in result.json()["detail"]
    assert client.get("/api/platform/products/" + product["id"]).status_code == 200
    assert sdk.copies == [] and writes == [] and sheets.deletes == []
    assert "stage=image_permissions" in caplog.text
    sdk.close.assert_called_once()


def test_permission_revoked_after_preflight_retains_image_only_when_confirmed(removal):
    _, _, sdk, sheets, writes, _, _ = removal
    sdk.items["own"]["capabilities"]["canTrash"] = True
    result = remove(removal, retain_untrashable_images=True)
    assert result.status_code == 200, result.text
    assert result.json()["drive"]["retained_image_ids"] == ["own"]
    assert result.json()["drive"]["trashed_image_ids"] == []
    assert writes == ["own"] and not sdk.items["own"].get("trashed")
    assert len(sdk.copies) == 2 and sheets.deletes


def test_missing_capability_uses_provider_result_and_logs_codes_without_secrets(removal, caplog):
    client, product, sdk, sheets, _, _, _ = removal
    sdk.items["own"].pop("capabilities")
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        result = remove(removal)
    assert result.status_code == 403
    assert "stage=image_trash" in caplog.text and "provider_status=403" in caplog.text
    assert "provider_reason=insufficientFilePermissions" in caplog.text
    for secret in ["private-token", "private-email", "private.example", "secret"]:
        assert secret not in caplog.text + result.text
    assert not sheets.deletes
    assert client.get("/api/platform/products/" + product["id"]).status_code == 200


@pytest.mark.parametrize("reason,status", [("storageQuotaExceeded", 503), ("dailyLimitExceeded", 503), ("forbidden", 403)])
def test_other_google_failures_never_report_success_or_delete_sheet(removal, monkeypatch, reason, status):
    client, product, sdk, sheets, _, _, _ = removal
    sdk.items["own"]["capabilities"]["canTrash"] = True
    monkeypatch.setattr(sdk, "update", lambda **kwargs: response(lambda: (_ for _ in ()).throw(denied(reason))))
    result = remove(removal, retain_untrashable_images=True)
    assert result.status_code == status and "private-token" not in result.text
    if reason == "dailyLimitExceeded":
        assert "límite de solicitudes" in result.text
    assert not sheets.deletes and not sdk.items["own"].get("trashed")
    assert client.get("/api/platform/products/" + product["id"]).status_code == 200


def test_retention_never_authorizes_an_image_outside_the_selected_catalog(removal):
    client, product, sdk, sheets, writes, _, value = removal
    with transaction() as db:
        db.add(ProductImage(tenant_id=value["platform_tenant"], product_id=product["id"], drive_file_id="foreign"))
    result = remove(removal, retain_untrashable_images=True)
    assert result.status_code == 409
    assert sdk.copies == [] and not sheets.deletes and writes == []
    assert not sdk.items["foreign"].get("trashed")
    assert client.get("/api/platform/products/" + product["id"]).status_code == 200


def test_sheet_write_permission_failure_keeps_product_and_reports_the_failed_stage(removal, monkeypatch, caplog):
    client, product, sdk, sheets, _, _, _ = removal
    monkeypatch.setattr(sheets, "batchUpdate", lambda **kwargs: response(lambda: (_ for _ in ()).throw(denied())))
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        result = remove(removal, retain_untrashable_images=True)
    assert result.status_code == 403 and "inventario_completo" in result.json()["detail"]
    assert "stage=sheet_delete" in caplog.text and "private-token" not in caplog.text
    assert client.get("/api/platform/products/" + product["id"]).status_code == 200
    assert len(sheets.rows) == 2 and not sdk.items["own"].get("trashed")
    sdk.close.assert_called_once()
    sheets.close.assert_called_once()


def test_viewer_cannot_use_retention_to_bypass_admin_role(removal):
    _, _, sdk, sheets, writes, _, value = removal
    value["email"] = "viewer@example.test"
    result = remove(removal, retain_untrashable_images=True)
    assert result.status_code == 403 and sdk.copies == [] and not sheets.deletes and writes == []


def test_shared_drive_capability_allows_trash_without_requiring_personal_ownership(removal, monkeypatch):
    _, _, sdk, sheets, _, _, _ = removal
    sdk.items["own"].update(ownedByMe=False, capabilities={"canTrash": True})
    monkeypatch.setattr(sdk, "update", DriveDouble.update.__get__(sdk))
    result = remove(removal)
    assert result.status_code == 200, result.text
    assert result.json()["drive"]["trashed_image_ids"] == ["own"]
    assert result.json()["drive"]["retained_image_ids"] == []
    assert sdk.items["own"]["trashed"] and sheets.deletes
