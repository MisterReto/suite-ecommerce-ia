"""Real HTTP edits and in-memory Sheets; no Google or store writes."""
from copy import deepcopy
from types import SimpleNamespace
import re

import pytest
from sqlalchemy import select, func

from test_catalog_platform import setup, create, ORIGIN
from test_sheet_catalog_sync import SheetDouble, DriveDouble, response
from catalog_platform import product_edit
from catalog_platform.database import transaction
from catalog_platform.models import Product, InventoryMovement
from inventory_schema import MASTER_COLUMNS
import studio_api as studio


class EditableSheet(SheetDouble):
    def __init__(self, rows):
        super().__init__(rows)
        self.writes = []
        self.failure = False

    def batchUpdate(self, **kwargs):
        def apply():
            if self.failure:
                raise ValueError("Drive temporalmente desconectado.")
            body = kwargs["body"]
            assert body["valueInputOption"] == "RAW"
            for entry in body["data"]:
                assert entry["range"].startswith("'Lista completa'!")
                match = re.search(r"!([A-Z]+)(\d+)$", entry["range"])
                column = sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(match[1]))) - 1
                index = int(match[2]) - 1
                while len(self.rows) <= index:
                    self.rows.append([])
                self.rows[index] += [""] * max(0, column + 1 - len(self.rows[index]))
                value = entry["values"][0][0]
                self.rows[index][column] = int(value) if isinstance(value, float) and value.is_integer() else value
            self.writes.append(deepcopy(body))
            return {}
        return response(apply)


@pytest.fixture
def drive_edit(setup, monkeypatch):
    client, value, _ = setup
    headers = list(MASTER_COLUMNS) + ["reserved", "", "", "", "atributo_nombre", "atributo_valor", "codigo_barras"]
    row = dict(sku="POCK41", tipo="simple", nombre_producto="Antes", Marca="Glico", precio=35,
        Existencias=10, imagenes="POCK41_1_hd.jpg", **{"Web link imagen": "=FORMULA()", "reserved": "keep"})
    sheets = EditableSheet([headers, [row.get(key, "") for key in headers]])
    drive = DriveDouble(value["platform_tenant"])
    monkeypatch.setattr(product_edit, "read_inventory", lambda *a: (drive, "sheet", []))
    monkeypatch.setattr(studio.runtime, "_get_sheets_service", lambda *a: sheets)
    return client, value, sheets


def test_edit_saves_drive_by_sku_preserving_images_formulas_and_other_columns(drive_edit):
    client, _, sheet = drive_edit
    product = create(client)
    result = client.put(f"/api/platform/products/{product['id']}", json={**product,
        "name": "Nombre editado", "tags": ["Chocolate"], "price": 42, "stock": 8,
        "barcode": "036000291452", "sync_drive": True}, headers=ORIGIN)
    assert result.status_code == 200, result.text
    assert result.json()["drive_saved"] is True
    row = dict(zip(sheet.rows[0], sheet.rows[1]))
    assert row["nombre_producto"] == "Nombre editado" and row["precio"] == 42 and row["Existencias"] == 8
    assert row["etiquetas"] == "Chocolate" and row["codigo_barras"] == "036000291452"
    assert row["imagenes"] == "POCK41_1_hd.jpg" and row["Web link imagen"] == "=FORMULA()" and row["reserved"] == "keep"
    assert len(sheet.rows) == 2 and len(sheet.writes) == 1


def test_failed_drive_edit_reports_pending_and_retry_does_not_duplicate_stock_or_rows(drive_edit):
    client, value, sheet = drive_edit
    product = create(client)
    sheet.failure = True
    payload = {**product, "sku": "POCK42", "name": "Actualizado", "stock": 7, "sync_drive": True}
    failed = client.put(f"/api/platform/products/{product['id']}", json=payload, headers=ORIGIN)
    assert failed.status_code == 200 and failed.json()["drive_saved"] is False
    assert "Drive temporalmente desconectado" in failed.json()["message"]
    sheet.failure = False
    result = client.put(f"/api/platform/products/{product['id']}", json={**failed.json()["product"], "sync_drive": True}, headers=ORIGIN)
    assert result.status_code == 200 and result.json()["drive_saved"] is True, result.text
    assert sheet.rows[1][2] == "POCK42" and len(sheet.rows) == 2
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.tenant_id == value["platform_tenant"], InventoryMovement.product_id == product["id"])) == 2


def test_duplicate_drive_sku_and_changed_columns_are_reported_without_writes(drive_edit):
    client, _, sheet = drive_edit
    product = create(client)
    sheet.rows.append(deepcopy(sheet.rows[1]))
    result = client.put(f"/api/platform/products/{product['id']}", json={**product, "sync_drive": True}, headers=ORIGIN)
    assert result.status_code == 200 and result.json()["drive_saved"] is False
    assert "duplicado" in result.json()["message"] and not sheet.writes


def test_new_catalog_form_saves_drive_and_stale_edit_cannot_write(drive_edit):
    client, _, sheet = drive_edit
    created = client.post("/api/platform/products", json={"sku": "NUEVO", "name": "Producto nuevo",
        "price": 20, "stock": 3, "sync_drive": True}, headers=ORIGIN)
    assert created.status_code == 201 and created.json()["drive_saved"] is True, created.text
    product = created.json()["product"]
    assert len(sheet.rows) == 3 and sheet.rows[2][2] == "NUEVO"
    original_version = product["version"]
    saved = client.put(f"/api/platform/products/{product['id']}", json={**product, "name": "Editado", "sync_drive": True}, headers=ORIGIN)
    assert saved.status_code == 200 and saved.json()["drive_saved"] is True
    writes = len(sheet.writes)
    stale = client.put(f"/api/platform/products/{product['id']}", json={**product,
        "version": original_version, "name": "Antiguo", "sync_drive": True}, headers=ORIGIN)
    assert stale.status_code == 409 and len(sheet.writes) == writes


def test_edit_can_add_a_variant_using_parent_sku_and_save_it_in_drive(drive_edit):
    client, _, sheet = drive_edit
    parent = create(client, sku="POCKFULL", product_type="variable", stock=None, price=None)
    parent_row = dict(sku="POCKFULL", tipo="variable", nombre_producto="Familia", Marca="Glico")
    sheet.rows.append([parent_row.get(key, "") for key in sheet.rows[0]])
    child = create(client)
    changed = client.put(f"/api/platform/products/{child['id']}", json={**child,
        "product_type": "variation", "parent_sku": parent["sku"], "attributes": {"Sabor": "Chocolate"},
        "sync_drive": True}, headers=ORIGIN)
    assert changed.status_code == 200 and changed.json()["drive_saved"] is True, changed.text
    assert sheet.rows[1][0] == "POCKFULL" and sheet.rows[1][1] == "variation"
    assert sheet.rows[1][18:20] == ["Sabor", "Chocolate"]


def test_changed_drive_schema_is_not_overwritten(drive_edit):
    client, _, sheet = drive_edit
    product = create(client)
    sheet.rows[0][3] = "otra_columna"
    result = client.put(f"/api/platform/products/{product['id']}", json={**product, "sync_drive": True}, headers=ORIGIN)
    assert result.status_code == 200 and result.json()["drive_saved"] is False
    assert "columnas" in result.json()["message"] and not sheet.writes


def test_parent_is_selected_and_returned_by_sku_for_creation_and_edit(setup):
    client, _, _ = setup
    parent = create(client, sku="POCKFULL", product_type="variable", stock=None, price=None)
    child = create(client, sku="FRESA", product_type="variation", parent_sku="pockfull", attributes={"Sabor": "Fresa"})
    assert child["parent_sku"] == "POCKFULL" and child["parent_id"] == parent["id"]
    assert client.get(f"/api/platform/products/{child['id']}").json()["product"]["parent_sku"] == "POCKFULL"
    simple = create(client, sku="CHOCO")
    changed = client.put(f"/api/platform/products/{simple['id']}", json={**simple,
        "product_type": "variation", "parent_sku": "POCKFULL", "parent_id": "untrusted-internal-id"}, headers=ORIGIN)
    assert changed.status_code == 200 and changed.json()["product"]["parent_id"] == parent["id"]


def test_parent_sku_is_scoped_to_the_tenant_and_must_be_a_variable(setup):
    client, _, _ = setup
    create(client, sku="SIMPLE")
    with transaction() as db:
        db.add(Product(tenant_id="other", sku="FOREIGNFULL", name="Otra tienda", product_type="variable"))
    for sku in ("SIMPLE", "FOREIGNFULL", "MISSING", ""):
        result = client.post("/api/platform/products", json={"sku": "CHILD", "name": "Hija", "product_type": "variation", "parent_sku": sku}, headers=ORIGIN)
        assert result.status_code == 422 and "SKU" in result.json()["detail"]
