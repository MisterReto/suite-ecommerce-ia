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
            "generated": {"id": "generated", "name": "imagenes_generadas", "mimeType": "application/vnd.google-apps.folder", "parents": [root]},
            "own": {"id": "own", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": ["generated"]},
            "shared": {"id": "shared", "name": "cover.jpg", "mimeType": "image/jpeg", "parents": ["generated"]},
            "foreign": {"id": "foreign", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": ["foreign-root"]},
            "foreign-root": {"id": "foreign-root", "parents": []},
        }
        self.copies = []

    def files(self):
        return self

    def get(self, fileId, **kwargs):
        return response(lambda: deepcopy(self.items[fileId]))

    def list(self, q, **kwargs):
        parent = re.search(r"'([^']+)' in parents", q)[1]
        name = re.search(r"name\s*=\s*'([^']+)'", q)
        return response(lambda: {"files": [deepcopy(item) for item in self.items.values()
            if parent in item.get("parents", []) and not item.get("trashed")
            and (not name or item.get("name") == name[1])
            and ("application/vnd.google-apps.folder" not in q or item.get("mimeType") == "application/vnd.google-apps.folder")
            and ("mimeType contains 'image/'" not in q or item.get("mimeType", "").startswith("image/"))]})

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


def test_image_names_ignore_root_backups_references_and_nested_copies():
    sdk = DriveDouble("catalog")
    for key, parent in (("root-copy", "catalog"), ("backup-copy", "backups"),
                        ("reference-copy", "references"), ("nested-copy", "nested")):
        sdk.items[key] = {"id": key, "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": [parent]}
    sdk.items["nested"] = {"id": "nested", "name": "references", "mimeType": "application/vnd.google-apps.folder", "parents": ["generated"]}
    drive = DriveService(sdk, "catalog")
    assert sheet_sync.named_images(drive, {"sprite.jpg"}) == {"sprite.jpg": "own"}


def test_real_duplicates_inside_generated_images_still_block():
    sdk = DriveDouble("catalog")
    sdk.items["duplicate"] = {"id": "duplicate", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": ["generated"]}
    with pytest.raises(ValueError, match="imagenes_generadas: sprite.jpg"):
        sheet_sync.named_images(DriveService(sdk, "catalog"), {"sprite.jpg"})


def test_absent_generated_folder_does_not_fall_back_to_catalog_root():
    sdk = DriveDouble("catalog")
    del sdk.items["generated"]
    sdk.items["own"]["parents"] = ["catalog"]
    assert sheet_sync.named_images(DriveService(sdk, "catalog"), {"sprite.jpg"}) == {}


def test_image_scan_paginates_only_the_generated_folder_and_deduplicates_ids(monkeypatch):
    sdk = DriveDouble("catalog")
    original = sdk.list
    queries = []
    def pages(q, **kwargs):
        queries.append(q)
        if "'generated' in parents" not in q:
            return original(q, **kwargs)
        assert "mimeType contains 'image/'" in q
        image = deepcopy(sdk.items["own"])
        if not kwargs.get("pageToken"):
            return response(lambda: {"files": [image], "nextPageToken": "second"})
        assert kwargs["pageToken"] == "second"
        return response(lambda: {"files": [image, deepcopy(sdk.items["shared"])]})
    monkeypatch.setattr(sdk, "list", pages)
    assert sheet_sync.named_images(DriveService(sdk, "catalog"), {"sprite.jpg", "cover.jpg"}) == {"sprite.jpg": "own", "cover.jpg": "shared"}
    assert len(queries) == 3 and all(" in parents" in q for q in queries)


def test_table_sync_uses_generated_images_despite_same_named_root_copy(setup, monkeypatch):
    client, value, _ = setup
    sdk = DriveDouble(value["platform_tenant"])
    sdk.items["root-copy"] = {"id": "root-copy", "name": "sprite.jpg", "mimeType": "image/jpeg", "parents": [value["platform_tenant"]]}
    monkeypatch.setattr(studio.runtime, "_get_drive_service", lambda *args: sdk)
    row = {"sku": "SPRITE", "nombre_producto": "Sprite", "imagenes": "sprite.jpg"}
    product_id = sheet_sync.sync_inventory_product(value, row, [row])
    with transaction() as db:
        assert list(db.scalars(select(ProductImage.drive_file_id).where(ProductImage.product_id == product_id))) == ["own"]


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


def test_native_table_sync_reads_fresh_sheet_and_mirrors_catalog(setup, monkeypatch):
    client, value, _ = setup
    row = {"sku": "SPRITE", "nombre_producto": "Sprite Zero", "categorias": "Bebidas>Jugos", "Existencias": 2, "precio": 35}
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (object(), "sheet", [row]))
    monkeypatch.setattr(sheet_sync, "DriveService", lambda *args: SimpleNamespace(owns=lambda *args: True))
    result = sheet_sync.sync_inventory(value, ["SPRITE"])
    assert result["updated"] == 1
    assert client.get("/api/platform/products").json()["items"][0]["sku"] == "SPRITE"
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (object(), "sheet", []))
    result = sheet_sync.sync_inventory(value, ["SPRITE"])
    assert result["updated"] == 0 and result["failed"] == 1
    assert result["warnings"][0]["sku"] == "SPRITE" and "falta" in result["warnings"][0]["message"]
    assert client.get("/api/platform/products").json()["total"] == 1


def test_native_bulk_sync_keeps_valid_products_and_preserves_family(setup, monkeypatch):
    client, value, _ = setup
    parent = {"sku": "FAMILYFULL", "nombre_producto": "Familia", "tipo": "variable", "categorias": "Dulces > Galletas"}
    child = {"sku": "CHILD", "sku_padre": "FAMILYFULL", "tipo": "variation", "nombre_producto": "Fresa", "precio": 35, "Existencias": 7}
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (object(), "sheet", [parent, child]))
    monkeypatch.setattr(sheet_sync, "DriveService", lambda *args: SimpleNamespace(owns=lambda *args: True))
    assert sheet_sync.sync_inventory(value, ["CHILD"])["updated"] == 2
    items = client.get("/api/platform/products").json()["items"]
    father = next(item for item in items if item["sku"] == "FAMILYFULL")
    assert father["stock"] is None and father["subcategory"] == "Galletas"
    assert next(item for item in items if item["sku"] == "CHILD")["parent_id"] == father["id"]
    invalid = {"sku": "INVALID", "nombre_producto": "Inválido", "tipo": "simple", "Existencias": -1}
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (object(), "sheet", [{**child, "Existencias": 9}, parent, invalid]))
    result = sheet_sync.sync_inventory(value, ["CHILD", "INVALID"])
    assert result["updated"] == 2 and result["failed"] == 1
    assert result["warnings"][0]["sku"] == "INVALID"
    assert "existencias" in result["warnings"][0]["message"]
    assert client.get("/api/platform/products").json()["total"] == 2
    assert client.get("/api/platform/products/" + next(item["id"] for item in items if item["sku"] == "CHILD")).json()["product"]["stock"] == 9


def bulk_source(monkeypatch, rows):
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (object(), "sheet", rows))
    monkeypatch.setattr(sheet_sync, "DriveService", lambda *args: SimpleNamespace(owns=lambda *args: True))


def test_bulk_sync_reports_missing_duplicates_and_bad_fields_without_repeating_stock(setup, monkeypatch):
    client, value, _ = setup
    rows = [{"sku": "GOOD", "nombre_producto": "Válido", "Existencias": 4},
            {"sku": "DUP", "nombre_producto": "Primero"}, {"sku": "DUP", "nombre_producto": "Segundo"},
            {"sku": "PRICE", "nombre_producto": "Precio inválido", "precio": "private-cell"},
            {"sku": "NAME", "nombre_producto": ""}]
    bulk_source(monkeypatch, rows)
    result = sheet_sync.sync_inventory(value, ["GOOD", "GOOD", "DUP", "MISSING", "PRICE", "NAME", "", "X" * 81])
    assert result["requested"] == 7 and result["updated"] == 1 and result["failed"] == 6
    issues = {item["sku"]: item["message"] for item in result["warnings"]}
    assert "duplicado" in issues["DUP"] and "falta" in issues["MISSING"]
    assert "precio" in issues["PRICE"] and "nombre" in issues["NAME"]
    assert "private-cell" not in str(result)
    assert sheet_sync.sync_inventory(value, ["GOOD"])["product_ids"] == result["product_ids"]
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id == result["product_ids"][0])) == 1
    assert client.get("/api/platform/products").json()["total"] == 1


@pytest.mark.parametrize("parent", [None, {"sku": "PARENTFULL", "nombre_producto": ""},
                                     {"sku": "PARENT", "nombre_producto": "Tipo simple"}])
def test_bulk_sync_skips_bad_parent_and_children_but_saves_unrelated_products(setup, monkeypatch, parent):
    client, value, _ = setup
    parent_sku = parent["sku"] if parent else "ABSENT"
    child = {"sku": "CHILD", "nombre_producto": "Variante", "tipo": "variation", "sku_padre": parent_sku}
    rows = [child, {"sku": "GOOD", "nombre_producto": "Válido"}] + ([parent] if parent else [])
    bulk_source(monkeypatch, rows)
    result = sheet_sync.sync_inventory(value, ["CHILD", "GOOD"])
    assert any(item["sku"] == "CHILD" and parent_sku in item["message"] for item in result["warnings"])
    assert {p["sku"] for p in client.get("/api/platform/products").json()["items"]} == ({"GOOD", "PARENT"} if parent_sku == "PARENT" else {"GOOD"})


def test_bulk_sync_invalid_sibling_does_not_block_valid_variant(setup, monkeypatch):
    client, value, _ = setup
    rows = [{"sku": "PARENTFULL", "nombre_producto": "Familia"},
            {"sku": "BAD", "nombre_producto": "Inválido", "tipo": "variation", "sku_padre": "PARENTFULL", "Existencias": -1},
            {"sku": "GOOD", "nombre_producto": "Válido", "tipo": "variation", "sku_padre": "PARENTFULL", "Existencias": 3}]
    bulk_source(monkeypatch, rows)
    result = sheet_sync.sync_inventory(value, ["BAD", "GOOD"])
    assert result["updated"] == 2 and result["failed"] == 1
    products = {p["sku"]: p for p in client.get("/api/platform/products").json()["items"]}
    assert products["GOOD"]["parent_id"] == products["PARENTFULL"]["id"]


def test_bulk_sync_real_database_failure_rolls_back_only_that_product(setup, monkeypatch):
    client, value, _ = setup
    existing = create(client, sku="B_FAIL", stock=2, category="Antes")
    rows = [{"sku": sku, "nombre_producto": "Actualizado", "Existencias": 8, "categorias": "Después"}
            for sku in ["A_GOOD", "B_FAIL", "C_GOOD"]]
    bulk_source(monkeypatch, rows)
    original = sheet_sync.mirror_rows
    def fail_after_write(db, value, root, selected, files, **kwargs):
        result = original(db, value, root, selected, files, **kwargs)
        if selected[0]["sku"] == "B_FAIL":
            db.add(Product(tenant_id=root, sku="B_FAIL", name="private-token"))
            db.flush()  # Real uniqueness violation; the session must recover via savepoint.
        return result
    monkeypatch.setattr(sheet_sync, "mirror_rows", fail_after_write)
    result = sheet_sync.sync_inventory(value, [row["sku"] for row in rows])
    assert result["updated"] == 2 and result["failed"] == 1
    assert result["warnings"][0]["sku"] == "B_FAIL" and "base de datos" in result["warnings"][0]["message"]
    assert "private-token" not in str(result) and "INSERT" not in str(result)
    product = client.get("/api/platform/products/" + existing["id"]).json()["product"]
    assert product["stock"] == 2 and product["category"] == "Antes" and product["name"] == existing["name"]
    assert client.get("/api/platform/products").json()["total"] == 3
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.product_id == existing["id"])) == 1


def test_bulk_sync_image_duplicates_and_missing_files_warn_without_losing_data(setup, monkeypatch):
    client, value, _ = setup
    sdk = DriveDouble(value["platform_tenant"])
    sdk.items["duplicate"] = {**sdk.items["own"], "id": "duplicate"}
    row = {"sku": "GOOD", "nombre_producto": "Producto", "imagenes": "sprite.jpg,cover.jpg,missing.jpg"}
    monkeypatch.setattr(sheet_sync, "read_inventory", lambda *args: (sdk, "sheet", [row]))
    result = sheet_sync.sync_inventory(value, ["GOOD"])
    assert result["updated"] == 1 and result["failed"] == 0
    assert {item["image"] for item in result["warnings"]} == {"sprite.jpg", "missing.jpg"}
    assert all(item["sku"] == "GOOD" for item in result["warnings"])
    with transaction() as db:
        assert list(db.scalars(select(ProductImage.drive_file_id).where(ProductImage.product_id == result["product_ids"][0]))) == ["shared"]


def test_bulk_sync_image_lookup_failure_is_sanitized_and_keeps_product_data(setup, monkeypatch):
    _, value, _ = setup
    bulk_source(monkeypatch, [{"sku": "GOOD", "nombre_producto": "Producto", "imagenes": "sprite.jpg"}])
    monkeypatch.setattr(sheet_sync, "named_images", Mock(side_effect=RuntimeError("private-token")))
    result = sheet_sync.sync_inventory(value, ["GOOD"])
    assert result["updated"] == 1 and result["failed"] == 0
    assert "permisos" in result["warnings"][0]["message"] and "private-token" not in str(result)


def test_bulk_sync_global_source_boundary_still_blocks_all_writes(setup, monkeypatch):
    client, value, _ = setup
    bulk_source(monkeypatch, [{"sku": "GOOD", "nombre_producto": "Producto"}])
    monkeypatch.setattr(sheet_sync, "DriveService", lambda *args: SimpleNamespace(owns=lambda *args: False))
    with pytest.raises(ValueError, match="autorizada"):
        sheet_sync.sync_inventory(value, ["GOOD"])
    assert client.get("/api/platform/products").json()["total"] == 0


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
