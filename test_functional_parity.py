"""Capture parity over HTTP and durable storage. No paid calls or live writes."""
import io
import json
import re
import secrets
import time
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from sqlalchemy import select, func
from catalog_capture import prepare_capture_updates, records_from_values
from inventory_schema import MASTER_COLUMNS
from catalog_platform import accounts, capture_bridge
from catalog_platform.database import transaction
from catalog_platform.models import GenerationJob, IntegrationAccount, Product, ProductImage, ProductVariant, uid
from catalog_platform.security import unseal
from creative_pipeline import IMAGE_MODEL, TEXT_MODEL
from test_catalog_platform import setup, ORIGIN
from test_studio_api import wait
import studio_api as studio


@pytest.fixture
def capture_store(setup, monkeypatch):
    client, value, drive = setup
    values = [list(MASTER_COLUMNS) + ["", "", "", "", "atributo_nombre", "atributo_valor", "codigo_barras"]]
    names = {}
    writes = []
    monkeypatch.setenv("SUITE_DRIVE_ONLY", "true")
    monkeypatch.setattr(studio.runtime.captura, "snapshot", lambda *a: (drive, "test-sheet", records_from_values(values)))
    monkeypatch.setattr(studio.runtime, "_preparar_estructura", lambda *a: (value["platform_tenant"], "original-images", "test-sheet", None))
    monkeypatch.setattr(studio.runtime, "_cargar_logo_marca", lambda *a: Image.new("RGBA", (64, 64), (100, 0, 80, 255)))
    monkeypatch.setattr(studio.runtime, "_buscar_archivo", lambda service, name, folder, *a: names.get(name))

    def upload(service, folder, name, path):
        result = drive.upload(path, name, folder)
        names[name] = result["id"]
        return result["id"]

    def append(session, sheet, record):
        planned = prepare_capture_updates(values, record)
        updated = deepcopy(values)
        for item in planned:
            match = re.search(r"!([A-Z]+)(\d+):([A-Z]+)(\d+)$", item["range"])
            if not match:
                continue
            column = 0
            for char in match[1]:
                column = column * 26 + ord(char) - 64
            column -= 1
            for offset, row in enumerate(item["values"]):
                index = int(match[2]) - 1 + offset
                while len(updated) <= index:
                    updated.append([""] * 21)
                while len(updated[index]) < column + len(row):
                    updated[index].append("")
                updated[index][column:column + len(row)] = row
        values[:] = updated
        writes.append(deepcopy(record))
        return sheet

    monkeypatch.setattr(studio.runtime, "_subir_imagen_drive", upload)
    monkeypatch.setattr(studio.runtime, "_agregar_fila_google_sheet", append)
    return client, value, drive, values, names, writes


def start(client, **updates):
    raw = io.BytesIO()
    Image.new("RGB", (120, 180), "red").save(raw, "JPEG")
    uploaded = client.post("/api/uploads", files={"image": ("pocky.jpg", raw.getvalue(), "image/jpeg")}, headers=ORIGIN)
    assert uploaded.status_code == 200, uploaded.text
    response = client.post("/api/capture", json={"front_id": uploaded.json()["id"], "context": "Etiqueta real"}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    product = studio.Product(name="Pocky Chocolate 40 g", brand="Glico", size="40 g", category="Dulces",
                             price=35, attribute="Sabor", attribute_value="Chocolate", **updates).model_dump()
    response = client.put("/api/draft", json=product, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return response.json()["draft"]["product"]


def sheet_row(values, sku="POCKFR40", name="Pocky Fresa 40 g", kind="simple", parent="", code=""):
    record = dict(sku=sku, nombre_producto=name, tipo=kind, sku_padre=parent, Marca="Glico", categorias="Dulces",
                  precio=30, Existencias=4, atributo_nombre="Sabor", atributo_valor="Fresa", codigo_barras=code)
    values.append([record.get(k, "") for k in MASTER_COLUMNS] + ["", "", "", "", "Sabor", "Fresa", code])


@pytest.mark.parametrize("pasted,personal", [
    pytest.param("AIza" + "P" * 35, "AIza" + "P" * 35, id="standard"),
    pytest.param("AQ." + "Ab0_-/+=" * 64, "AQ." + "Ab0_-/+=" * 64, id="long-opaque"),
    pytest.param(" \nAQ." + "Ab0_-/+=" * 64 + "\r\n", "AQ." + "Ab0_-/+=" * 64, id="clipboard-whitespace"),
])
def test_key_is_encrypted_persistent_and_never_uses_render(capture_store, monkeypatch, pasted, personal):
    client, value, *_ = capture_store
    monkeypatch.setenv("AI_API_KEY", "R" * 25)
    assert client.post("/api/settings", json={"api_key": pasted}, headers=ORIGIN).status_code == 200
    with transaction() as db:
        row = accounts.account(db, value["platform_tenant"], value["email"], "gemini")
        assert personal not in row.encrypted_credentials
        assert unseal(row.encrypted_credentials) == {"api_key": personal}
    sid = secrets.token_urlsafe(24)
    restored = dict(email=value["email"], expires_at=time.time()+600, creds=value["creds"])
    studio.runtime.SESSIONS[sid] = restored
    client.cookies.set("session_id", sid)
    try:
        response = client.get("/api/session")
        assert response.status_code == 200, response.text
        assert response.json()["gemini_source"] == "user_settings"
        assert restored["gemini_key"] == personal
        assert personal not in response.text and "R"*25 not in response.text
        assert client.delete("/api/settings/gemini", headers=ORIGIN).status_code == 200
        assert client.get("/api/session").json()["gemini_configured"] is False
        assert "gemini_key" not in restored
    finally:
        studio.runtime._eliminar_sesion(sid)
        client.cookies.set("session_id", value["session_id"])


@pytest.mark.parametrize("pasted", [
    pytest.param("", id="empty"),
    pytest.param("AIza-short", id="incomplete"),
    pytest.param("P" * 25 + " " + "P" * 25, id="internal-space"),
    pytest.param("P" * 25 + "\n" + "P" * 25, id="internal-newline"),
    pytest.param("P" * 25 + "\x00", id="control"),
    pytest.param("P" * 25 + "\u200b", id="invisible-unicode"),
    pytest.param("P" * 4097, id="oversized"),
])
def test_bad_key_paste_does_not_replace_saved_credentials(capture_store, pasted):
    client, value, *_ = capture_store
    response = client.post("/api/settings", json={"api_key": pasted}, headers=ORIGIN)
    assert response.status_code == 422
    assert value["gemini_key"] == "test-key-no-spend"
    with transaction() as db:
        assert accounts.gemini_for(db, value["platform_tenant"], value["email"]) == "test-key-no-spend"
    if len(pasted) >= 20:
        assert pasted not in response.text


def test_worker_reloads_updated_key_and_stale_google_snapshot_cannot_undo_it(capture_store):
    _, value, *_ = capture_store
    with transaction() as db:
        accounts.persist(db, value["platform_tenant"], value["email"], value)
        old = accounts.load(db, value["platform_tenant"], value["email"])
        accounts.save_gemini(db, value["platform_tenant"], value["email"], "N"*25)
    with transaction() as db:
        accounts.persist(db, value["platform_tenant"], value["email"], old)
        new = accounts.load(db, value["platform_tenant"], value["email"])
        assert new["gemini_key"] == "N"*25
        accounts.delete_gemini(db, value["platform_tenant"], value["email"])
    with transaction() as db:
        assert "gemini_key" not in accounts.load(db, value["platform_tenant"], value["email"])


def test_credentials_are_isolated_by_actor_and_store(capture_store):
    _, value, *_ = capture_store
    with transaction() as db:
        accounts.save_gemini(db, value["platform_tenant"], "editor@example.test", "E"*25)
        accounts.save_gemini(db, "another-store", value["email"], "S"*25)
    with transaction() as db:
        assert accounts.gemini_for(db, value["platform_tenant"], value["email"]) == "test-key-no-spend"
        assert accounts.gemini_for(db, value["platform_tenant"], "editor@example.test") == "E"*25
        assert accounts.gemini_for(db, "another-store", value["email"]) == "S"*25
        assert accounts.gemini_for(db, value["platform_tenant"], "viewer@example.test") is None


def test_key_check_lists_models_without_generating(capture_store, monkeypatch):
    client, *_ = capture_store
    sdk = Mock()
    sdk.__enter__ = Mock(return_value=sdk)
    sdk.__exit__ = Mock(return_value=False)
    sdk.models.list.return_value = [SimpleNamespace(name="models/"+TEXT_MODEL), SimpleNamespace(name="models/"+IMAGE_MODEL)]
    monkeypatch.setattr("google.genai.Client", Mock(return_value=sdk))
    response = client.post("/api/settings/gemini/test", json={}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json()["image_model_available"] and response.json()["text_model_available"]
    sdk.models.generate_content.assert_not_called()


def test_selected_store_is_restored_before_render_default(capture_store, monkeypatch):
    _, value, *_ = capture_store
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "render-default-other-store")
    new_login = {"email":value["email"]}
    accounts.restore(new_login)
    assert new_login["carpeta_raiz_id_manual"] == value["platform_tenant"]
    assert new_login["gemini_key"] == "test-key-no-spend"


def test_viewer_cannot_change_capture_or_credentials(capture_store):
    client, value, *_ = capture_store
    start(client)
    value["email"] = "viewer@example.test"
    for endpoint, method, data in [("/api/draft","PUT",studio.Product().model_dump()),
            ("/api/save","POST",{"confirm":True}), ("/api/capture-notes","PUT",{"context":"change"}),
            ("/api/settings","POST",{"api_key":"V"*25}), ("/api/family-cover","POST",{}),
            ("/api/draft","DELETE",None)]:
        response = client.request(method, endpoint, json=data, headers=ORIGIN)
        assert response.status_code == 403, (endpoint,response.text)


def test_other_actor_cannot_read_capture_files_or_restore_draft(capture_store):
    client, value, *_ = capture_store
    start(client)
    key = value["studio_draft"]["front_id"]
    sid = secrets.token_urlsafe(24)
    other = dict(email="editor@example.test", platform_tenant=value["platform_tenant"],
                 carpeta_raiz_id_manual=value["platform_tenant"], expires_at=time.time()+600, creds=value["creds"])
    studio.runtime.SESSIONS[sid] = other
    client.cookies.set("session_id",sid)
    try:
        assert client.get("/api/session").json()["draft"] is None
        assert client.get("/api/files/"+key).status_code == 404
        assert client.post("/api/capture",json={"front_id":key},headers=ORIGIN).status_code == 404
    finally:
        studio.runtime._eliminar_sesion(sid)
        client.cookies.set("session_id",value["session_id"])


def test_rejected_fields_can_be_corrected_before_any_sheet_write(capture_store):
    client, value, _, _, _, writes = capture_store
    p = start(client)
    p["name"] = ""
    assert client.put("/api/draft",json=p,headers=ORIGIN).status_code == 200
    rejected = wait(client,client.post("/api/save",json={"confirm":True},headers=ORIGIN))
    assert rejected["job"]["status"] == "failed" and not writes
    assert "save_phase" not in value["studio_draft"]
    p["name"] = "Pocky Chocolate 40 g"
    assert client.put("/api/draft",json=p,headers=ORIGIN).status_code == 200
    saved = wait(client,client.post("/api/save",json={"confirm":True},headers=ORIGIN))
    assert saved["job"]["status"] == "completed" and len(writes) == 1


def test_existing_master_parent_is_reused_when_sheet_is_missing_it(capture_store):
    client, value, _, values, _, writes = capture_store
    with transaction() as db:
        parent = Product(tenant_id=value["platform_tenant"],sku="GLIPOCFULL",name="Pocky",brand="Glico",
                         product_type="variable",price=None,stock=None,attributes={"Sabor":["Fresa"]})
        db.add(parent); db.flush(); parent_id = parent.id
    p = start(client,kind="Variable")
    p.update(parent_sku="GLIPOCFULL",parent_name="Pocky",parent_mode="Usar padre existente")
    assert client.put("/api/draft",json=p,headers=ORIGIN).status_code == 200
    cover = wait(client,client.post("/api/family-cover",headers=ORIGIN))
    assert cover["job"]["status"] == "completed",cover
    saved = wait(client,client.post("/api/save",json={"confirm":True},headers=ORIGIN))
    assert saved["job"]["status"] == "completed" and saved["draft"]["sync_status"] == "synced",saved
    assert len(writes) == 1 and len(records_from_values(values)) == 2
    with transaction() as db:
        child = db.get(Product,saved["draft"]["master_product_id"])
        assert child.parent_id == parent_id
        assert db.get(Product,parent_id).attributes == {"Sabor":["Fresa","Chocolate"]}


def test_photo_analysis_fills_editable_fields_and_marks_unknowns(capture_store, monkeypatch):
    client, value, *_ = capture_store
    start(client)
    model = Mock()
    model.models.generate_content.return_value = SimpleNamespace(text=json.dumps({"nombre": "Pocky Chocolate", "marca": "Glico", "gramaje": None,
        "categoria": "No verificada", "variante": "Chocolate", "tipo_producto": "Galleta", "atributos": {"Sabor":"Chocolate"},
        "desc_corta":"Galletas de chocolate.", "desc_larga":"Producto fotografiado.", "etiquetas":[]}))
    monkeypatch.setattr(studio, "GeminiClient", Mock(return_value=model))
    monkeypatch.setattr(studio, "read_barcodes", lambda path: [])
    result = wait(client, client.post("/api/analyze", headers=ORIGIN))
    assert result["job"]["status"] == "completed", result
    p = result["draft"]["product"]
    assert p["name"] == "Pocky Chocolate" and p["brand"] == "Glico"
    assert p["size"] == "" and p["category"] == ""
    assert "gramaje" in p["uncertain_fields"] and "categoria" in p["uncertain_fields"]
    assert p["variant"] == "Chocolate" and p["attribute"] == "Sabor"
    assert p["sku"] == studio.runtime.generar_sku_logica(p["name"], p["brand"], "")
    assert len(p["sku"]) == 10 and p["barcode"] == ""
    assert client.put("/api/draft", json={**p, "size":"40 g"}, headers=ORIGIN).status_code == 200
    model.models.generate_content.assert_called_once()


def test_exact_barcode_skips_ai_and_refuses_a_duplicate(capture_store, monkeypatch):
    client, value, _, values, _, writes = capture_store
    sheet_row(values, code="4006381333931")
    start(client)
    ai = Mock(side_effect=AssertionError("An exact barcode must not call Gemini"))
    monkeypatch.setattr(studio, "GeminiClient", ai)
    monkeypatch.setattr(studio, "read_barcodes", lambda p: ["4006381333931"])
    result = wait(client, client.post("/api/analyze", headers=ORIGIN))
    assert result["job"]["status"] == "completed", result
    assert result["draft"]["identity_review"]["case"] == "existing"
    assert result["draft"]["product"]["sku"] == "4006381333931"
    assert result["draft"]["identity_review"]["duplicate"]["sku"] == "POCKFR40"
    rejected = wait(client, client.post("/api/save", json={"confirm":True}, headers=ORIGIN))
    assert rejected["job"]["status"] == "failed" and writes == []
    ai.assert_not_called()


@pytest.mark.parametrize("scanned,seen,expected", [
    (["036000291452"], "4006381333931", "036000291452"),
    (["00036000291452"], "", "00036000291452"),
    (["96385074"], "", "96385074"),
    ([], "4006381333931", "4006381333931"),
    ([], "4006381333932", ""),
    ([], "No se alcanza a leer", ""),
    ([], "", ""),
])
def test_analysis_uses_readable_gtin_or_the_existing_ten_character_logic(capture_store, monkeypatch, scanned, seen, expected):
    client, *_ = capture_store
    start(client)
    errors = []
    original_error = studio.error_message
    def report_error(exc, value):
        errors.append(f"{type(exc).__name__}: {exc}")
        return original_error(exc, value)
    monkeypatch.setattr(studio, "error_message", report_error)
    model = Mock()
    model.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
        "nombre": "Pocky Chocolate", "marca": "Glico", "gramaje": "40 g", "codigo_barras": seen}))
    monkeypatch.setattr(studio, "GeminiClient", Mock(return_value=model))
    monkeypatch.setattr(studio, "read_barcodes", lambda path: scanned)
    result = wait(client, client.post("/api/analyze", headers=ORIGIN))
    assert result["job"]["status"] == "completed", (result["job"], errors)
    product = result["draft"]["product"]
    assert product["barcode"] == expected
    assert product["sku"] == (expected or studio.runtime.generar_sku_logica("Pocky Chocolate", "Glico", "40 g"))
    if not expected:
        assert len(product["sku"]) == 10


def test_manual_barcode_normalizes_sku_and_invalid_input_preserves_the_draft(capture_store):
    client, *_ = capture_store
    product = start(client)
    changed = client.put("/api/draft", json={**product, "sku": "CUSTOM", "barcode": "0 36000-291452"}, headers=ORIGIN)
    assert changed.status_code == 200, changed.text
    canonical = changed.json()["draft"]["product"]
    assert canonical["sku"] == canonical["barcode"] == "036000291452"
    rejected = client.put("/api/draft", json={**canonical, "barcode": "036000291453"}, headers=ORIGIN)
    assert rejected.status_code == 422
    assert client.get("/api/session").json()["draft"]["product"] == canonical
    cleared = client.put("/api/draft", json={**canonical, "barcode": "", "sku": "CUSTOM"}, headers=ORIGIN)
    assert cleared.status_code == 200
    fallback = cleared.json()["draft"]["product"]
    assert fallback["sku"] == studio.runtime.generar_sku_logica(product["name"], product["brand"], product["size"])
    assert len(fallback["sku"]) == 10 and fallback["barcode"] == ""


def test_parent_uses_matching_variants_without_rewriting_existing_catalog(capture_store):
    client, _, _, values, _, writes = capture_store
    sheet_row(values, code="4006381340007")
    product = start(client, kind="Variable", barcode="4006381333931")
    old = deepcopy(values)
    proposed = client.get("/api/parents")
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["parent_sku"] == "40063813xxxxx"
    assert values == old and writes == []
    sheet_row(values, sku="40063813xxxxx", name="Otra familia", kind="variable")
    collision = client.get("/api/parents")
    assert collision.status_code == 422 and "ya existe" in collision.text
    sheet_row(values, sku="GLIPOCFULL", name="Pocky", kind="variable")
    selected = {**product, "parent_sku": "GLIPOCFULL", "parent_mode": "Usar padre existente"}
    assert client.put("/api/draft", json=selected, headers=ORIGIN).status_code == 200
    assert client.get("/api/parents").json()["parent_sku"] == "GLIPOCFULL"


def test_new_flavor_uses_existing_family_without_ai(capture_store, monkeypatch):
    client, _, _, values, *_ = capture_store
    sheet_row(values, sku="GLIPOCFULL", name="Pocky", kind="variable")
    sheet_row(values, kind="variation", parent="GLIPOCFULL")
    start(client)
    ai = Mock(side_effect=AssertionError("Catalog match must not spend tokens"))
    monkeypatch.setattr(studio.runtime, "buscar_variantes_por_imagen", ai)
    result = wait(client, client.post("/api/find-variants", headers=ORIGIN))
    assert result["job"]["status"] == "completed", result
    review = result["draft"]["identity_review"]
    assert review["case"] == "existing_parent" and review["suggested"] == "GLIPOCFULL"
    assert any(r["sku"] == "POCKFR40" for r in review["candidates"])
    ai.assert_not_called()


def test_matching_brand_alone_never_invents_family(capture_store):
    client, _, _, values, *_ = capture_store
    sheet_row(values, sku="GLIPREFULL", name="Glico Pretz", kind="variable")
    start(client)
    review = client.post("/api/check-product", json={}, headers=ORIGIN).json()
    assert review["case"] == "simple" and not review["suggested"]


def test_simple_save_preserves_reference_and_mirrors_master_once(capture_store):
    client, value, drive, values, names, writes = capture_store
    product = start(client)
    sku = product["sku"]
    result = wait(client, client.post("/api/save", json={"confirm":True}, headers=ORIGIN))
    assert result["job"]["status"] == "completed", result
    assert result["draft"]["sync_status"] == "synced"
    assert len(writes) == 1 and f"{sku}_referencia_frente.jpg" in names
    assert any(r["sku"] == sku for r in records_from_values(values))
    with transaction() as db:
        p = db.get(Product, result["draft"]["master_product_id"])
        assert p.product_type == "simple" and p.stock == 0 and p.price == 35
        image = db.scalar(select(ProductImage).where(ProductImage.product_id==p.id, ProductImage.role=="reference"))
        assert image and image.drive_file_id == names[f"{sku}_referencia_frente.jpg"]
    assert client.post("/api/save", json={"confirm":True}, headers=ORIGIN).status_code == 200
    assert len(writes) == 1
    assert all(u["folder"] == "original-images" for u in drive.uploads if "_referencia_" in u["name"])


def test_saved_job_marker_survives_loss_before_final_draft_checkpoint(capture_store):
    from catalog_platform.studio_jobs import record_saved
    client, value, drive, _, _, writes = capture_store
    start(client)
    current = value["studio_draft"]
    current.update(saved="💾 TEST-INTEGRATION guardado", sync_status="pending_repair")
    uploads = len(drive.uploads)
    record_saved(value, current)
    assert len(drive.uploads) == uploads and not writes
    value.pop("studio_draft")
    recovered = client.get("/api/session").json()["draft"]
    assert recovered["saved"] == current["saved"]
    assert recovered["sync_status"] == "pending_repair"
    assert client.post("/api/save", json={"confirm":True}, headers=ORIGIN).status_code == 200
    assert not writes  # Recovery cannot repeat an already accepted Sheet write.
    assert client.delete("/api/draft", headers=ORIGIN).status_code == 200
    record_saved(value, current)
    assert client.get("/api/session").json()["draft"] is None


def test_worker_completion_recovers_into_matching_draft_but_never_revives_clear(capture_store, monkeypatch):
    client, value, *_ = capture_store
    monkeypatch.setenv("STUDIO_IMAGE_JOBS", "worker")
    start(client)
    current = value["studio_draft"]
    with transaction() as db:
        state = unseal(accounts.account(db, value["platform_tenant"], value["email"], "capture_draft").encrypted_credentials)
        file_id = state["references"][0]
        payload = {"capture":{k:deepcopy(current[k]) for k in ("revision","context","product")},
                   "references":state["references"],"results":{"1_hd":{"id":file_id,"raw_id":file_id,
                   "history":[],"approved":False,"message":"Imagen sintética terminada"}}}
        db.add(GenerationJob(tenant_id=value["platform_tenant"],actor=value["email"],kind="studio_generation",
                             request_key=uid(),status="completed",model=IMAGE_MODEL,payload=payload))
    revised = {**current["product"], "name":"Nombre revisado después de solicitar la imagen"}
    assert client.put("/api/draft", json=revised, headers=ORIGIN).status_code == 200
    value.pop("studio_draft")
    recovered = client.get("/api/session").json()["draft"]
    assert recovered["product"]["name"] == revised["name"]
    assert "1_hd" in recovered["images"]
    assert client.get("/api/files/"+recovered["images"]["1_hd"]["id"]).status_code == 200
    assert client.delete("/api/draft", headers=ORIGIN).status_code == 200
    assert client.get("/api/session").json()["draft"] is None


@pytest.mark.parametrize("code,expected", [("", "GLIPOCFULL"), ("4006381333931", "400638xxxxxxx")])
def test_new_parent_cover_and_variant_are_atomic_in_master(capture_store, code, expected):
    client, value, _, values, names, writes = capture_store
    p = start(client, kind="Variable", barcode=code)
    proposed = client.get("/api/parents").json()
    assert proposed["parent_name"] == "Pocky" and proposed["parent_sku"] == expected
    p.update(parent_sku=proposed["parent_sku"], parent_name=proposed["parent_name"])
    assert client.put("/api/draft", json=p, headers=ORIGIN).status_code == 200
    cover = wait(client, client.post("/api/family-cover", headers=ORIGIN))
    assert cover["job"]["status"] == "completed", cover
    assert "1 foto" in cover["draft"]["cover_message"]
    assert client.get("/api/files/"+cover["draft"]["cover_id"]).status_code == 200
    saved = wait(client, client.post("/api/save", json={"confirm":True}, headers=ORIGIN))
    assert saved["job"]["status"] == "completed", saved
    assert saved["draft"]["sync_status"] == "synced"
    with transaction() as db:
        child = db.get(Product, saved["draft"]["master_product_id"])
        parent = db.get(Product, child.parent_id)
        assert child.product_type == "variation" and child.attributes == {"Sabor":"Chocolate", "Tamaño":"40 g"}
        assert parent.product_type == "variable" and parent.price is None and parent.stock is None
        assert parent.sku == expected and not parent.barcode
        assert child.sku == p["sku"] and (child.barcode or "") == code
        assert parent.attributes == {"Sabor":["Chocolate"]}
        assert db.scalar(select(ProductVariant).where(ProductVariant.child_product_id==child.id)).product_id == parent.id
        assert db.scalar(select(ProductImage).where(ProductImage.product_id==parent.id, ProductImage.role=="cover"))
    assert len(writes) == 1 and len(records_from_values(values)) == 2


def test_mirror_failure_is_visible_and_repair_never_repeats_sheet_write(capture_store, monkeypatch):
    client, _, _, _, _, writes = capture_store
    start(client)
    mirror = capture_bridge.mirror
    monkeypatch.setattr(capture_bridge, "mirror", Mock(side_effect=RuntimeError("SQL unavailable")))
    result = wait(client, client.post("/api/save", json={"confirm":True}, headers=ORIGIN))
    assert result["job"]["status"] == "completed", result
    assert result["draft"]["saved"] and result["draft"]["sync_status"] == "pending_repair"
    monkeypatch.setattr(capture_bridge, "mirror", mirror)
    repaired = wait(client, client.post("/api/capture-sync", headers=ORIGIN))
    assert repaired["job"]["status"] == "completed" and repaired["draft"]["sync_status"] == "synced", repaired
    assert len(writes) == 1


def test_lost_sheet_response_is_verified_before_retry(capture_store, monkeypatch):
    client, _, _, _, _, writes = capture_store
    start(client)
    writer = studio.runtime.captura.save
    def lost(*args):
        result = writer(*args)
        assert result.startswith("💾"), result
        raise RuntimeError("Response lost after Sheet accepted")
    monkeypatch.setattr(studio.runtime.captura, "save", lost)
    first = wait(client, client.post("/api/save", json={"confirm":True}, headers=ORIGIN))
    assert first["job"]["status"] == "failed" and len(writes) == 1
    second = wait(client, client.post("/api/save", json={"confirm":True}, headers=ORIGIN))
    assert second["job"]["status"] == "completed" and second["draft"]["saved"], second
    assert len(writes) == 1


def test_draft_recovers_photos_and_notes_after_process_session_loss(capture_store):
    client, value, *_ = capture_store
    start(client)
    assert client.put("/api/capture-notes", json={"context":"Observación nueva"}, headers=ORIGIN).status_code == 200
    previous_id = value["studio_draft"]["front_id"]
    old_sid = value["session_id"]
    studio.runtime._eliminar_sesion(old_sid)
    new_sid = secrets.token_urlsafe(24)
    restored = dict(email=value["email"], expires_at=time.time()+600, creds=value["creds"], carpeta_raiz_id_manual=value["platform_tenant"])
    studio.runtime.SESSIONS[new_sid] = restored
    client.cookies.set("session_id", new_sid)
    try:
        status = client.get("/api/session")
        assert status.status_code == 200, status.text
        draft = status.json()["draft"]
        assert draft["product"]["name"] == "Pocky Chocolate 40 g" and draft["context"] == "Observación nueva"
        assert draft["front_id"] != previous_id
        assert client.get("/api/files/"+draft["front_id"]).status_code == 200
        assert client.get("/api/files/"+previous_id).status_code == 404
    finally:
        studio.runtime._eliminar_sesion(new_sid)


def test_master_duplicate_is_found_even_when_sheet_has_no_row(capture_store):
    client, value, *_ = capture_store
    with transaction() as db:
        p = Product(tenant_id=value["platform_tenant"], sku="POCKCH40", name="Pocky Chocolate 40 g", brand="Glico", price=35)
        db.add(p)
    start(client)
    checked = client.post("/api/check-product", json={}, headers=ORIGIN).json()
    assert checked["status"] == "duplicate" and checked["duplicate"]["_source"] == "PostgreSQL"
    assert checked["duplicate"]["product_id"]


def test_mirror_parent_and_child_rollback_together(capture_store):
    client, value, _, values, *_ = capture_store
    p = start(client, kind="Variable")
    p.update(parent_sku="GLIPOCFULL", parent_name="Pocky")
    current = {"revision":"bad-parent-rollback", "product":p}
    sheet_row(values, sku="GLIPOCFULL", name="Pocky", kind="simple")
    sheet_row(values, sku=p["sku"], name="Pocky Chocolate 40 g", kind="variation", parent="MISSINGFULL")
    with pytest.raises(ValueError, match="padre"):
        capture_bridge.mirror_records(value, current, records_from_values(values))
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Product).where(Product.tenant_id==value["platform_tenant"])) == 0


def test_upload_exif_and_real_file_type_are_checked(capture_store):
    client, *_ = capture_store
    raw = io.BytesIO()
    image = Image.new("RGB", (120,180), "blue")
    exif = Image.Exif(); exif[274] = 6
    image.save(raw, "JPEG", exif=exif)
    response = client.post("/api/uploads", files={"image":("vertical.jpg",raw.getvalue(),"image/jpeg")}, headers=ORIGIN)
    assert response.status_code == 200 and (response.json()["width"],response.json()["height"]) == (180,120)
    assert client.post("/api/uploads", files={"image":("fake.jpg",b"<script>bad</script>","image/jpeg")}, headers=ORIGIN).status_code == 422


def test_woo_candidate_queries_are_read_only_and_tenant_scoped(capture_store, monkeypatch):
    _, value, *_ = capture_store
    monkeypatch.setenv("SUITE_DRIVE_ONLY", "false")
    monkeypatch.setenv("WOOCOMMERCE_TENANT_ID", value["platform_tenant"])
    client = Mock()
    client.config.configured = True
    client.find_entity_by_sku.return_value = None
    client.request.return_value = [{"sku":"POCKFR40", "name":"Pocky Fresa 40 g", "brands":[{"name":"Glico"}], "attributes":[]}]
    constructor = Mock(return_value=client)
    monkeypatch.setattr("woocommerce_client.WooCommerceClient", constructor)
    rows, note = capture_bridge.woo_rows(value, studio.Product(sku="POCKCH40",name="Pocky Chocolate 40 g").model_dump())
    assert rows[0]["_source"] == "WooCommerce"
    assert all(call.args[0] == "GET" for call in client.request.call_args_list)
    constructor.reset_mock()
    assert capture_bridge.woo_rows({**value,"platform_tenant":"foreign"}, studio.Product().model_dump())[0] == []
    constructor.assert_not_called()
