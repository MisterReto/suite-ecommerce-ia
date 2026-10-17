"""Shared-by-link Drive responses must preserve the same catalog boundary."""
from copy import deepcopy
import json
import re
import secrets
from types import SimpleNamespace

import pytest

from drive_service import DriveService
from test_catalog_platform import setup, ORIGIN
import studio_api as studio


FOLDER = "application/vnd.google-apps.folder"
SHEET = "application/vnd.google-apps.spreadsheet"


class SharedDrive:
    def __init__(self, hide_parents):
        self.hide_parents = hide_parents
        self.items = {
            "catalog": dict(id="catalog", name="Proyecto_IA", mimeType=FOLDER),
            "sheet": dict(id="sheet", name="inventario_completo", mimeType=SHEET, parents=["catalog"]),
            "images": dict(id="images", name="imagenes_generadas", mimeType=FOLDER, parents=["catalog"]),
            "photo": dict(id="photo", name="pocky_1_hd.jpg", mimeType="image/jpeg", parents=["images"]),
            "foreign": dict(id="foreign", name="inventario_completo", mimeType=SHEET, parents=["other-root"]),
            "other-root": dict(id="other-root", name="Other catalog", mimeType=FOLDER, parents=[]),
        }
        self.queries = []

    def files(self):
        return self

    def result(self, item, fields):
        item = deepcopy(item)
        if self.hide_parents:
            item.pop("parents", None)
        return {key: val for key, val in item.items() if key in fields}

    def get(self, fileId, fields, **kwargs):
        return SimpleNamespace(execute=lambda: self.result(self.items[fileId], fields))

    def list(self, q, fields, **kwargs):
        self.queries.append(q)
        parent = re.search(r"'([^']+)' in parents", q)[1]
        name = re.search(r"name\s*=\s*'([^']+)'", q)
        rows = []
        for item in self.items.values():
            if parent not in item.get("parents", []) or ("trashed=false" in q.replace(" ", "") and item.get("trashed")):
                continue
            is_folder = item.get("mimeType") == FOLDER
            if name and item["name"] != name[1] and not (" or " in q and is_folder):
                continue
            if FOLDER in q and not name and not is_folder:
                continue
            if SHEET in q and item.get("mimeType") != SHEET:
                continue
            rows.append(self.result(item, fields))
        return SimpleNamespace(execute=lambda: {"files": rows})


@pytest.mark.parametrize("hide_parents", [False, True])
def test_owner_and_collaborator_prepare_the_same_existing_inventory(monkeypatch, hide_parents):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "catalog")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet")
    drive = DriveService(SharedDrive(hide_parents))
    assert studio.runtime._preparar_estructura(drive, {"email": "collaborator@example.test"}) == (
        "catalog", "images", "sheet", None)


def test_shared_images_remain_accessible_without_disclosing_parents():
    sdk = SharedDrive(True)
    drive = DriveService(sdk, "catalog")
    assert drive.owns("photo")
    assert drive.metadata("photo")["id"] == "photo"
    assert drive.generated_images_folder() == "images"
    assert all(" in parents" in query for query in sdk.queries)


@pytest.mark.parametrize("hide_parents", [False, True])
def test_accessible_foreign_sheet_with_identical_name_is_still_rejected(monkeypatch, hide_parents):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "catalog")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "foreign")
    drive = DriveService(SharedDrive(hide_parents), "catalog")
    assert not drive.owns("foreign")
    with pytest.raises(ValueError, match="carpeta autorizada"):
        studio.runtime._preparar_estructura(drive, {"email": "collaborator@example.test"})


def test_shared_shortcuts_and_trashed_files_do_not_expand_the_boundary():
    sdk = SharedDrive(True)
    sdk.items["shortcut"] = dict(id="shortcut", name="Other catalog", mimeType="application/vnd.google-apps.shortcut",
                                 parents=["catalog"], shortcutDetails={"targetId": "other-root"})
    sdk.items["removed"] = dict(id="removed", name="removed.jpg", mimeType="image/jpeg", parents=["images"], trashed=True)
    drive = DriveService(sdk, "catalog")
    assert not drive.owns("foreign")
    assert not drive.owns("removed")
    assert drive.owns("removed", include_trashed=True)
    assert all("'other-root' in parents" not in query for query in sdk.queries)


def test_personal_folder_does_not_use_the_default_stores_sheet(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "other-root")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "foreign")
    sdk = SharedDrive(True)
    original = sdk.get
    def get(fileId, **kwargs):
        assert fileId != "foreign", "A personal store must not read another store's inventory"
        return original(fileId, **kwargs)
    monkeypatch.setattr(sdk, "get", get)
    assert studio.runtime._preparar_estructura(DriveService(sdk), {
        "email": "collaborator@example.test", "carpeta_raiz_id_manual": "catalog"
    }) == ("catalog", "images", "sheet", None)


def test_configured_inventory_still_requires_a_native_spreadsheet(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "catalog")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet")
    sdk = SharedDrive(True)
    sdk.items["sheet"]["mimeType"] = "text/csv"
    with pytest.raises(ValueError, match="hoja nativa"):
        studio.runtime._preparar_estructura(DriveService(sdk), {"email": "collaborator@example.test"})


def test_membership_proof_paginates_and_has_a_request_limit(monkeypatch):
    sdk = SharedDrive(True)
    original = sdk.list
    def pages(q, **kwargs):
        if kwargs.get("pageToken") == "second":
            return original(q, **kwargs)
        return SimpleNamespace(execute=lambda: {"files": [], "nextPageToken": "second"})
    monkeypatch.setattr(sdk, "list", pages)
    assert DriveService(sdk, "catalog").owns("photo")
    calls = []
    def endless(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(execute=lambda: {"files": [], "nextPageToken": "endless"})
    monkeypatch.setattr(sdk, "list", endless)
    assert not DriveService(sdk, "catalog").owns("photo")
    assert len(calls) == 100


def test_sheet_preview_and_taxonomy_work_for_three_authorized_accounts(setup, monkeypatch):
    import pandas as pd
    client, value, _ = setup
    emails = ["admin@example.test", "second@example.test", "third@example.test"]
    monkeypatch.setenv("APP_ROLE_MAP", json.dumps(dict.fromkeys(emails, "admin")))
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "catalog")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet")
    value.update(platform_tenant="catalog", carpeta_raiz_id_manual="catalog")
    reads = []
    def drive(session):
        reads.append(session["email"])
        assert session["creds"]["token"] == session["email"]
        return DriveService(SharedDrive(hide_parents=session["email"] != emails[0]))
    monkeypatch.setattr(studio.runtime, "_get_drive_service", drive)
    monkeypatch.setattr(studio.runtime, "_get_sheets_service", lambda *args: object())
    monkeypatch.setattr(studio.runtime, "_leer_google_sheet", lambda service, sheet: pd.DataFrame([
        {"sku": "POCKY40", "nombre_producto": "Pocky chocolate", "categorias": "Dulces>Galletas", "etiquetas": "Chocolate"}]))
    for email in emails:
        sid = secrets.token_urlsafe(24)
        session = dict(value, email=email, session_id=sid, creds={"token": email})
        session.pop("capture_snapshot", None)
        studio.runtime.SESSIONS[sid] = session
        client.cookies.clear()
        client.cookies.set("session_id", sid)
        try:
            response = client.post("/api/platform/import/sheets", headers=ORIGIN)
            assert response.status_code == 200, response.text
            assert response.json()["rows"] == 1 and response.json()["sample"][0]["sku"] == "POCKY40"
            taxonomy = client.get("/api/catalog-taxonomy")
            assert taxonomy.status_code == 200, taxonomy.text
            assert taxonomy.json()["tags"] == ["Chocolate"]
        finally:
            studio.runtime._eliminar_sesion(sid)
    assert set(reads) == set(emails)
