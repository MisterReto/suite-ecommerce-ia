"""Sheets/Drive/catalog regressions using in-memory Google services only."""
from copy import deepcopy
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select, func

from inventory_schema import MASTER_COLUMNS, normalize_product_row
from catalog_capture import records_from_values
from sheets_service import SheetsService
from drive_service import DriveService
from catalog_platform import sheet_sync, imports, queue
from catalog_platform.database import transaction
from catalog_platform.models import Product, ProductImage, InventoryMovement, GenerationJob, uid
from test_catalog_platform import setup, create, ORIGIN
import studio_api as studio


def response(callback):
    return SimpleNamespace(execute=callback)


class SheetDouble:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.deletes = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        def read():
            cells = kwargs.get("range")
            if not cells:
                return {"sheets": [{"properties": {"sheetId": 7, "title": "Lista completa", "gridProperties": {"rowCount": len(self.rows) + 2}}}]}
            match = re.search(r"!([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$", cells)
            first = sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(match[1]))) - 1
            last = sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(match[3] or match[1])))
            a, b = int(match[2]) - 1, int(match[4] or match[2])
            return {"values": [row[first:last] for row in self.rows[a:b]]}
        return response(read)

    def batchUpdate(self, **kwargs):
        def update():
            for operation in kwargs["body"]["requests"]:
                target = operation["deleteDimension"]["range"]
                assert target["sheetId"] == 7 and target["dimension"] == "ROWS"
                self.deletes.append(deepcopy(target))
                del self.rows[target["startIndex"]:target["endIndex"]]
            return {}
        return response(update)


class DriveDouble:
    def __init__(self, root):
        self.items = {
            "sheet": {"id": "sheet", "name": "inventario_completo", "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [root]},
            "own": {"id": "own", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": [root]},
            "shared": {"id": "shared", "name": "cover.jpg", "mimeType": "image/jpeg", "parents": [root]},
            "foreign": {"id": "foreign", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": ["foreign-root"]},
            "foreign-root": {"id": "foreign-root", "parents": []},
        }
        self.copies = []

    def files(self):
        return self

    def get(self, fileId, **kwargs):
        return response(lambda: deepcopy(self.items[fileId]))

    def list(self, q, **kwargs):
        name = re.search(r"name = '([^']+)'", q)[1]
        return response(lambda: {"files": [deepcopy(item) for item in self.items.values() if item.get("name") == name and not item.get("trashed")]})

    def copy(self, fileId, body, **kwargs):
        def backup():
            copied = {**deepcopy(self.items[fileId]), **body, "id": "backup-" + str(len(self.copies))}
            self.copies.append(copied)
            return copied
        return response(backup)

    def update(self, fileId, body, **kwargs):
        def update():
            self.items[fileId].update(body)
            return deepcopy(self.items[fileId])
        return response(update)


@pytest.mark.parametrize("path", ["Bebidas>Jugos y Sodas", " Bebidas > Jugos y Sodas ", "Bebidas >Jugos y Sodas"])
def test_paths_read_any_spacing_and_write_canonical_format(path):
    row = {"sku": "SPRITE", "nombre_producto": "Sprite Zero", "categorias": path}
    data, errors = imports.normalize([row])
    assert not errors
    assert (data[0]["category"], data[0]["subcategory"]) == ("Bebidas", "Jugos y Sodas")
    assert normalize_product_row(row)["categorias"] == "Bebidas>Jugos y Sodas"
    import ai_app
    assert ai_app._canonical_row(row)[8] == "Bebidas>Jugos y Sodas"


def test_drive_categories_use_headers_even_when_columns_move():
    headers = ["sku", "etiquetas", "categorias", "Marca", "nombre_producto", "Existencias", "precio"]
    rows = records_from_values([headers, ["SPRITE", "Refresco", "Bebidas>Jugos y Sodas", "Sprite", "Sprite Zero", 4, 35]])
    from catalog_taxonomy import choices_from_rows
    choices = choices_from_rows(rows)
    assert choices["categories"] == ["Bebidas"]
    assert choices["subcategories"] == {"Bebidas": ["Jugos y Sodas"]}
    assert rows[0]["Marca"] == "Sprite" and rows[0]["precio"] == 35
    legacy = records_from_values([["sku", "categoria", "subcategoria"], ["OLD", "Dulces", "Galletas"]])
    assert legacy[0]["categorias"] == "Dulces>Galletas"


def test_personal_folder_works_when_global_sheet_is_inaccessible(monkeypatch):
    import pandas as pd
    import catalog_taxonomy
    from googleapiclient.errors import HttpError
    monkeypatch.setenv("GOOGLE_SHEET_ID", "global-sheet")
    boundary = Mock()
    boundary.owns.side_effect = HttpError(SimpleNamespace(status=403, reason="Forbidden"), b"{}")
    monkeypatch.setattr("drive_service.DriveService", lambda *args: boundary)
    runtime = SimpleNamespace(_get_drive_service=lambda *args: object(), NOMBRE_GOOGLE_SHEET="inventario_completo",
                              _buscar_archivo=lambda *args: "personal-sheet", _get_sheets_service=lambda *args: object(),
                              _leer_google_sheet=lambda service, sheet: pd.DataFrame([{"sku": "PERSONAL", "categorias": "Hogar>Vajilla"}]))
    client, sheet, rows = catalog_taxonomy.read_inventory(runtime, {"carpeta_raiz_id_manual": "personal-root"})
    assert sheet == "personal-sheet" and rows[0]["categorias"] == "Hogar>Vajilla"


def test_sheet_delete_targets_exact_sku_and_preserves_neighbors():
    client = SheetDouble([["nombre_producto", "sku", "categorias"], ["Pocky", "KEEP", "Dulces"], ["Sprite", "DELETE", "Bebidas"], ["Tea", "LAST", "Bebidas"]])
    sheets = SheetsService(client, "sheet")
    assert sheets.delete_sku("DELETE")["deleted"]
    assert [row[1] for row in client.rows[1:]] == ["KEEP", "LAST"]
    assert client.deletes == [{"sheetId": 7, "dimension": "ROWS", "startIndex": 2, "endIndex": 3}]
    assert sheets.delete_sku("DELETE")["already_absent"]
    client.rows.append(["Duplicate", "KEEP", "Dulces"])
    with pytest.raises(ValueError, match="duplicado"):
        sheets.delete_sku("KEEP")
    assert len(client.deletes) == 1


def test_table_sync_appears_in_app_and_updates_without_duplicate_stock(setup, monkeypatch):
    client, value, _ = setup
    row = {"sku": "7501055363193", "tipo": "simple", "nombre_producto": "Sprite Zero", "Marca": "Sprite", "categorias": "Bebidas>Jugos y Sodas", "precio": 35, "Existencias": 4}
    monkeypatch.setattr(studio.runtime, "_get_drive_service", lambda *args: object())
    first = sheet_sync.sync_inventory_product(value, row, [row])
    changed = {**row, "Existencias": 7, "precio": 38}
    assert sheet_sync.sync_inventory_product(value, changed, [changed]) == first
    assert sheet_sync.sync_inventory_product(value, changed, [changed]) == first
    products = client.get("/api/platform/products").json()["items"]
    assert len(products) == 1
    assert products[0]["category"] == "Bebidas" and products[0]["subcategory"] == "Jugos y Sodas"
    assert products[0]["stock"] == 7 and products[0]["price"] == 38
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id == first)) == 2
    assert sheet_sync.sync_inventory_product(value, row, [row]) == first
    assert client.get("/api/platform/products").json()["items"][0]["stock"] == 4
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id == first)) == 3


def test_table_sync_keeps_parent_child_relations(setup, monkeypatch):
    client, value, _ = setup
    parent = {"sku": "GLICOFULL", "tipo": "variable", "nombre_producto": "Pocky", "Marca": "Glico", "categorias": "Dulces>Galletas"}
    child = {"sku": "POCKFR40", "sku_padre": "GLICOFULL", "tipo": "variation", "nombre_producto": "Pocky Fresa 40 g", "Marca": "Glico", "precio": 35, "Existencias": 4}
    monkeypatch.setattr(studio.runtime, "_get_drive_service", lambda *args: object())
    child_id = sheet_sync.sync_inventory_product(value, child, [parent, child])
    items = client.get("/api/platform/products").json()["items"]
    assert len(items) == 2
    father = next(item for item in items if item["sku"] == "GLICOFULL")
    assert next(item for item in items if item["id"] == child_id)["parent_id"] == father["id"]
    assert father["price"] is None and father["stock"] is None


def test_stale_table_sync_never_recreates_a_deleted_sheet_product(setup, monkeypatch):
    client, value, _ = setup
    product = create(client)
    assert client.request("DELETE", f"/api/platform/products/{product['id']}", json={"confirm": True, "version": product["version"]}, headers=ORIGIN).status_code == 200
    monkeypatch.setattr(studio.runtime, "_get_drive_service", lambda *args: object())
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (object(), "sheet", []))
    with pytest.raises(ValueError, match="eliminado"):
        sheet_sync.sync_inventory_product(value, {"sku": product["sku"], "nombre_producto": product["name"]}, [])
    assert client.get("/api/platform/products").json()["total"] == 0


def test_single_table_publication_mirrors_verified_result_to_catalog(setup, monkeypatch):
    client, value, _ = setup
    import product_web
    row = {"sku": "SPRITE", "nombre_producto": "Sprite Zero", "categorias": "Bebidas>Jugos", "Existencias": 2, "precio": 35}
    monkeypatch.setattr(product_web.media_web, "_direct_inventory_context", lambda *args: ("sheet", [row], object()))
    wc = Mock()
    wc.config.write_enabled = True
    wc.find_entity_by_sku.return_value = {"id": 5}
    monkeypatch.setattr(product_web, "WooCommerceClient", lambda: wc)
    monkeypatch.setattr(product_web, "sync_complete_product", lambda **kwargs: {"backend_verified": True})
    monkeypatch.setattr(studio.runtime, "_get_drive_service", lambda *args: object())
    result = product_web._full_sync(value, "SPRITE")
    assert result["catalog_product_id"]
    assert client.get("/api/platform/products").json()["items"][0]["sku"] == "SPRITE"


def test_delete_removes_sheet_and_trashes_only_own_images_with_backups(setup, monkeypatch):
    client, value, _ = setup
    product = create(client, sku="SPRITE")
    other = create(client, sku="KEEP")
    row = {"sku": "SPRITE", "imagenes": "sprite.jpg,cover.jpg"}
    rows = [row, {"sku": "KEEP", "imagenes": "cover.jpg"}]
    sdk = DriveDouble(value["platform_tenant"])
    drive = DriveService(sdk, value["platform_tenant"])
    monkeypatch.setattr(drive, "working_folder", lambda *args: "backups")
    monkeypatch.setattr(sheet_sync, "DriveService", lambda *args: drive)
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (sdk, "sheet", rows))
    sheets = SheetDouble([["sku", "imagenes"], ["SPRITE", "sprite.jpg,cover.jpg"], ["KEEP", "cover.jpg"]])
    monkeypatch.setattr(studio.runtime, "_get_sheets_service", lambda *args: sheets)
    with transaction() as db:
        for pid, fid in [(product["id"], "own"), (product["id"], "shared"), (other["id"], "shared")]:
            db.add(ProductImage(tenant_id=value["platform_tenant"], product_id=pid, drive_file_id=fid))
    body = {"confirm": True, "version": product["version"], "delete_from_drive": True}
    result = client.request("DELETE", f"/api/platform/products/{product['id']}", json=body, headers=ORIGIN)
    assert result.status_code == 200, result.text
    assert sdk.items["own"]["trashed"]
    assert not sdk.items["shared"].get("trashed") and not sdk.items["foreign"].get("trashed")
    assert [row[0] for row in sheets.rows[1:]] == ["KEEP"]
    assert len(sdk.copies) == 2 and result.json()["drive"]["trashed_image_ids"] == ["own"]
    assert client.get("/api/platform/products").json()["total"] == 1
    replay = client.request("DELETE", f"/api/platform/products/{product['id']}", json=body, headers=ORIGIN).json()
    assert replay["replayed"] and replay["drive"] == result.json()["drive"]
    assert len(sdk.copies) == 2


def test_drive_failure_does_not_report_product_deleted(setup, monkeypatch):
    client, _, _ = setup
    product = create(client)
    monkeypatch.setattr(sheet_sync, "delete_from_drive", Mock(side_effect=RuntimeError("private-token")))
    result = client.request("DELETE", f"/api/platform/products/{product['id']}", json={"confirm": True, "version": product["version"], "delete_from_drive": True}, headers=ORIGIN)
    assert result.status_code == 503 and "private-token" not in result.text
    assert client.get(f"/api/platform/products/{product['id']}").status_code == 200


def test_import_attaches_historic_images_to_existing_product(setup, monkeypatch):
    client, value, drive = setup
    product = create(client)
    data, errors = imports.normalize([{"sku": product["sku"], "nombre_producto": product["name"], "imagenes": "sprite.jpg"}])
    assert not errors
    with transaction() as db:
        job = GenerationJob(tenant_id=value["platform_tenant"], actor=value["email"], request_key=uid(), kind="import", payload={"rows": data, "checksum": "test"})
        db.add(job)
        db.flush()
        job_id = job.id
    monkeypatch.setattr(studio.runtime, "_preparar_estructura", lambda *args: (value["platform_tenant"], "images", "sheet", None))
    monkeypatch.setattr(drive, "list", lambda *args, **kwargs: [{"name": "sprite.jpg", "id": "own"}], raising=False)
    attach = Mock()
    monkeypatch.setattr(imports, "attach_historic_images", attach)
    claimed = queue.claim("import-owner", job_id)
    assert imports.execute_import(claimed, value, drive, "import-owner")
    assert attach.call_args.args[2] == product["id"]
    assert client.get("/api/platform/products").json()["total"] == 1
