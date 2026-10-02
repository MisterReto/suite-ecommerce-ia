"""End-to-end capture callbacks with real local images and fake remote services."""
import os
from pathlib import Path
import secrets
from unittest.mock import MagicMock

import pandas as pd
from PIL import Image
import pytest
import zxingcpp

os.environ.update(GOOGLE_CLIENT_ID="test", GOOGLE_CLIENT_SECRET="test", GOOGLE_REDIRECT_URI="https://example.com/auth/callback", GRADIO_ANALYTICS_ENABLED="False", SUITE_SERVICE_ROLE="main")
import product_web_ai
import app
import ai_app
from catalog_capture import records_from_values
from product_capture import NEW_PARENT, EXISTING_PARENT, read_barcodes
from test_catalog_capture import values, PARENT, CHILD


@pytest.fixture
def capture(monkeypatch):
    session = {"file_namespace": secrets.token_urlsafe(20)}
    monkeypatch.setattr(app, "_validar_sesion", lambda *args, **kwargs: (session, None))
    monkeypatch.setattr(app, "_cargar_df", lambda *args: (MagicMock(), "sheet", pd.DataFrame()))
    monkeypatch.setattr(app, "_preparar_estructura", lambda *args: ("root", "images", "sheet", None))
    monkeypatch.setattr(app, "_cargar_logo_marca", lambda *args: Image.new("RGBA", (64,64), (100,0,80,255)))
    monkeypatch.setattr(app, "GeminiClient", MagicMock(side_effect=AssertionError("No paid calls for capture checks or family covers")))
    path = Path(f"/tmp/{session['file_namespace']}_base_gen_frontal.jpg")
    Image.new("RGB", (700,900), "orange").save(path)
    yield session, str(path)
    path.unlink(missing_ok=True)
    for info in session.get("family_covers", {}).values():
        Path(info["path"]).unlink(missing_ok=True)


def test_reads_a_real_rotated_barcode_image(tmp_path):
    code = zxingcpp.create_barcode("7501031311309", zxingcpp.BarcodeFormat.EAN13)
    image = Image.fromarray(code.to_image(scale=4)).rotate(90, expand=True)
    path = tmp_path / "barcode.png"
    image.save(path)
    assert read_barcodes(str(path)) == ["7501031311309"]


def test_no_existing_parent_proposes_new_family_and_builds_cover_without_gemini(capture):
    session, path = capture
    updates = app.captura.load_parents("Variable", EXISTING_PARENT, "Panko 1 kg", "Brand", "PANK1KG", None, None)
    parent = updates[1]["value"]
    assert parent.endswith("FULL") and updates[5]["value"] == NEW_PARENT
    preview, message, token = app.captura.cover("Variable", NEW_PARENT, parent, "Panko", "PANK1KG", [path], None)
    assert "1 foto(s) reales" in message and token
    with Image.open(preview) as image:
        assert image.size == (1200,1200) and image.format == "JPEG"
    assert app.captura.cover("Variable", NEW_PARENT, parent, "Panko", "PANK1KG", [path], None)[2] == token


def test_existing_parent_dropdown_excludes_children_and_reuses_attribute(capture, monkeypatch):
    session, _ = capture
    monkeypatch.setattr(app, "_cargar_df", lambda *args: (MagicMock(), "sheet", pd.DataFrame([PARENT, CHILD])))
    updates = app.captura.load_parents("Variable", EXISTING_PARENT, "Panko 1 kg", "Brand", "PANK1KG", None, None)
    assert updates[0]["choices"] == [("Panko · Brand · PANKFULL", "PANKFULL")]
    assert updates[1]["value"] == "PANKFULL" and updates[4]["value"] == "Tamaño"


def test_save_links_new_parent_and_barcode_without_auto_publication(capture, monkeypatch):
    _, path = capture
    upload, append = MagicMock(), MagicMock()
    monkeypatch.setattr(app, "_subir_imagen_drive", upload)
    monkeypatch.setattr(app, "_agregar_fila_google_sheet", append)
    _, _, token = app.captura.cover("Variable", NEW_PARENT, "PANKFULL", "Panko", "PANK1KG", [path], None)
    result = app.captura.save("PANK1KG", "Variable", "PANKFULL", "Panko 1 kg", "Brand", "1 kg", "Tamaño", "1 kg", 40,
                             "Alimentos", "Harinas", "panko", "Panko 1 kg.", "Para empanizar.", "036000291452", NEW_PARENT, "Panko", token, None)
    assert "guardado" in result
    record = append.call_args.args[2]
    assert record['tipo'] == 'variation' and record['codigo_barras'] == '036000291452'
    assert record['_new_parent']['tipo'] == 'variable' and record['_new_parent']['sku'] == 'PANKFULL'
    assert record['_parent_cover'].startswith('PANKFULL_portada_')
    upload.assert_called_once()


def test_cover_token_from_another_session_or_family_cannot_be_saved(capture, monkeypatch):
    session, path = capture
    _, _, token = app.captura.cover("Variable", NEW_PARENT, "PANKFULL", "Panko", "PANK1KG", [path], None)
    append = MagicMock()
    monkeypatch.setattr(app, "_agregar_fila_google_sheet", append)
    monkeypatch.setattr(app, "_validar_sesion", lambda *args, **kwargs: ({}, None))
    result = app.captura.save("PANK1KG", "Variable", "PANKFULL", "Panko 1 kg", "Brand", "1 kg", "Tamaño", "1 kg", 40,
                             "Alimentos", "Harinas", "", "", "", "", NEW_PARENT, "Panko", token, None)
    assert 'portada' in result and '⛔' in result
    append.assert_not_called()


def test_duplicate_blocks_drive_upload_and_append(capture, monkeypatch):
    session, path = capture
    monkeypatch.setattr(app, "_cargar_df", lambda *args: (MagicMock(), "sheet", pd.DataFrame([PARENT, CHILD])))
    monkeypatch.setattr(app, "_buscar_archivo", lambda *args: None)
    _, _, token = app.captura.cover("Variable", EXISTING_PARENT, "PANKFULL", "Panko", "NEW", [path], None)
    upload, append = MagicMock(), MagicMock()
    monkeypatch.setattr(app, "_subir_imagen_drive", upload)
    monkeypatch.setattr(app, "_agregar_fila_google_sheet", append)
    result = app.captura.save("NEW", "Variable", "PANKFULL", "Panko 500 g", "Brand", "500g", "Tamaño", "500 g", 40,
                             "Alimentos", "Harinas", "", "", "", "", EXISTING_PARENT, "Panko", token, None)
    assert 'ya existe' in result
    upload.assert_not_called()
    append.assert_not_called()


def test_fresh_sheet_duplicate_blocks_single_atomic_write(capture, monkeypatch):
    sheet = MagicMock()
    sheet.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {'values': values(PARENT, CHILD)}
    monkeypatch.setattr(app, '_get_sheets_service', lambda *args: sheet)
    with pytest.raises(ValueError, match='ya existe'):
        ai_app._append_master_row({}, 'sheet', dict(CHILD, sku='NEW'))
    sheet.spreadsheets.return_value.values.return_value.batchUpdate.assert_not_called()


def test_parent_and_child_are_written_once_and_small_grid_is_extended(capture, monkeypatch):
    sheet = MagicMock()
    sheet.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {'values': values()}
    sheet.spreadsheets.return_value.get.return_value.execute.return_value = {'sheets':[{'properties':{'title':'Lista completa','sheetId':7,'gridProperties':{'columnCount':20}}}]}
    monkeypatch.setattr(app, '_get_sheets_service', lambda *args: sheet)
    ai_app._append_master_row({}, 'sheet', dict(CHILD, _new_parent=PARENT))
    write = sheet.spreadsheets.return_value.values.return_value.batchUpdate
    write.assert_called_once()
    updates = write.call_args.kwargs['body']['data']
    assert len([u for u in updates if ':U' in u['range'] and not u['range'].endswith('S1:U1')]) == 2
    sheet.spreadsheets.return_value.batchUpdate.assert_called_once()
