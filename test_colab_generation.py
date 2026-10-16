"""Self-contained Colab and real prompt adapter regressions; synthetic Gemini only."""
import base64
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import zlib

from PIL import Image, ImageDraw
import pytest

from colab.generation_backup import ColabGenerator
import creative_pipeline
from tools.build_colab_generation import build, extract, source_at


class FakeGemini:
    def __init__(self):
        self.models = self
        self.calls = []
        self.fail_image = False

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["model"] == "gemini-2.5-flash":
            if "quality inspector" in str(kwargs["contents"]):
                return SimpleNamespace(text=json.dumps({"aprobada": False, "puntuacion": 60,
                    "errores": ["Fix package geometry"], "resumen": "Revisa la geometría"}), candidates=[])
            return SimpleNamespace(text=json.dumps({"lifestyle": "An adult naturally tasting the exact food, original package visible nearby in warm daylight.",
                "comercial": "An artistic vibrant advertising hero with expressive color and dimensional illustration around the original package.",
                "interaction": "eat", "ads_found": False, "note": "Escena original"}), candidates=[])
        if self.fail_image:
            self.fail_image = False
            raise TimeoutError("secret-provider-token")
        picture = Image.new("RGB", (1024, 1024), "purple")
        ImageDraw.Draw(picture).rectangle((300, 200, 700, 800), fill="orange")
        buffer = io.BytesIO()
        picture.save(buffer, "PNG")
        part = SimpleNamespace(thought=False, inline_data=SimpleNamespace(mime_type="image/png", data=buffer.getvalue()))
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


@pytest.fixture
def motor(tmp_path, monkeypatch):
    import google.genai.types as types
    contract = ModuleType("app_generation_contract")
    contract.__file__ = str(tmp_path / "app_generation_contract.py")
    exec("import os,re,json\nfrom google.genai import types\n" + extract(source_at("app.py").decode(), {
        "PROMPT_HD", "PUNTUACION_MINIMA_QA", "MODELO_TEXTO", "ERRORES_IA", "_imagen_para_ia", "_extraer_json", "_validar_con_vision"}), contract.__dict__)
    monkeypatch.setitem(sys.modules, "app_generation_contract", contract)
    Image.new("RGBA", (100, 100), (255, 0, 0, 180)).save(tmp_path / "logo_rincon_asia.png")
    Image.new("RGB", (200, 300), "blue").save(tmp_path / "reference.jpg")
    (tmp_path / "inventario_completo.csv").write_text("sku,nombre_producto,Marca,categorias,referencias_locales\n00123,Pocky,Glico,Dulces>Galletas,reference.jpg\n")
    fake = FakeGemini()
    instance = ColabGenerator(tmp_path, client=fake)
    return instance, fake


def test_audit_preserves_leading_zero_sku_and_never_calls_provider(motor):
    instance, fake = motor
    report = instance.audit()
    assert report.iloc[0]["sku"] == "00123"
    assert report.iloc[0]["imagenes_faltantes"] == "1_hd,2_uso,3_comercial"
    assert fake.calls == []
    with pytest.raises(ValueError, match="confirma"):
        instance.batch()
    assert fake.calls == []


def test_uses_one_shared_brief_and_exact_app_slots_then_saves_only_on_approval(motor):
    instance, fake = motor
    result = instance.batch(confirm=True, workers=1)
    assert list(result.status) == ["candidate"] * 3
    assert len([call for call in fake.calls if call["model"] == "gemini-2.5-flash"]) == 1
    images = [call for call in fake.calls if call["model"] == "gemini-3.1-flash-image"]
    assert len(images) == 3
    assert instance.contract.PROMPT_HD in images[0]["contents"][-1]
    assert all(creative_pipeline.FIDELITY in call["contents"][-1] for call in images)
    assert all(call["config"].image_config.aspect_ratio == "1:1" for call in images)
    assert not instance.output.exists()
    assert instance.audit().iloc[0]["por_revisar"] == "1_hd,2_uso,3_comercial"
    instance.batch(confirm=True)
    assert len(fake.calls) == 4, "Re-running does not charge for staged images"
    with pytest.raises(ValueError):
        instance.approve(skus=["00123"])
    saved = instance.approve(skus=["00123"], slots=["1_hd"], confirm=True)
    assert Path(saved[0]).name == "00123_1_hd.jpg"
    assert (instance.output / "00123_1_hd_raw.jpg").is_file()
    assert not (instance.output / "00123_2_uso.jpg").exists()


def test_corrections_use_raw_original_references_and_history_without_overwriting(motor):
    instance, fake = motor
    instance.batch(slots=["1_hd"], confirm=True)
    previous = dict(instance._record("00123", "1_hd"))
    instance.correct("00123", "1_hd", "Conserva la geometría", confirm=True)
    last = fake.calls[-1]
    assert "PREVIOUS GENERATED IMAGE TO EDIT" in str(last["contents"])
    assert "Conserva la geometría" in last["contents"][-1]
    # The second attached image is the previous unbranded raw, compressed by the app helper.
    from gemini_gateway import image_part
    attachments = [part for part in last["contents"] if hasattr(part, "inline_data")]
    assert attachments[-1].inline_data.data == image_part(previous["raw"]).inline_data.data
    assert Path(previous["raw"]).exists() and Path(previous["image"]).exists()
    assert instance._record("00123", "1_hd")["history"] == ["Conserva la geometría"]
    assert not instance.output.exists()


def test_uncertain_result_does_not_retry_and_other_slots_continue(motor):
    instance, fake = motor
    fake.fail_image = True
    result = instance.batch(confirm=True, workers=1)
    assert list(result.status) == ["warning", "candidate", "candidate"]
    assert "secret-provider-token" not in str(result.to_dict())
    assert instance.audit().iloc[0]["resultado_incierto"] == "1_hd"
    before = len(fake.calls)
    instance.batch(confirm=True)
    assert len(fake.calls) == before
    instance.allow_retry("00123", "1_hd", confirm=True)
    instance.batch(slots=["1_hd"], confirm=True)
    assert len(fake.calls) == before + 1


def test_regeneration_preserves_canonical_until_explicit_approval_and_creates_backup(motor):
    instance, fake = motor
    instance.batch(slots=["1_hd"], confirm=True)
    instance.approve(skus=["00123"], confirm=True)
    canonical = instance.output / "00123_1_hd.jpg"
    old = canonical.read_bytes()
    instance.regenerate("00123", "1_hd", confirm=True)
    assert canonical.read_bytes() == old
    assert "PREVIOUS GENERATED IMAGE TO EDIT" not in str(fake.calls[-1]["contents"])
    instance.approve(skus=["00123"], confirm=True)
    assert any(p.read_bytes() == old for p in (instance.work / "backups").glob("*/00123_1_hd.jpg"))


def test_optional_qa_uses_exact_inspector_and_never_regenerates_automatically(motor):
    instance, fake = motor
    instance.batch(slots=["1_hd"], automatic_review=True, confirm=True)
    entry = instance._record("00123", "1_hd")
    assert entry["qa"]["aprobada"] is False and entry["qa"]["puntuacion"] == 60
    assert entry["status"] == "candidate"
    assert len(fake.calls) == 2


def test_style_selection_uses_two_direct_commercial_examples_with_original_png_priority(motor):
    instance, fake = motor
    instance.output.mkdir()
    for name in ("old_3.png", "recent_3_comercial.jpg", "catalog_1_hd.jpg"):
        Image.new("RGB", (1200, 1200), "orange").save(instance.output / name)
    nested = instance.output / "backups"
    nested.mkdir()
    Image.new("RGB", (1200, 1200), "blue").save(nested / "foreign_3.png")
    instance.batch(slots=["3_comercial"], confirm=True)
    assert len(instance.styles) == 2
    assert len([p for p in fake.calls[-1]["contents"] if isinstance(p, str) and p.startswith("STYLE ONLY")]) == 2


def test_notebook_embeds_unchanged_modules_and_compression_without_outputs(tmp_path):
    original = tmp_path / "original.ipynb"
    original.write_text(json.dumps({"cells": [{}, {"source": ["print('legacy compression')"]}], "metadata": {}}))
    target = tmp_path / "backup.ipynb"
    build(original, target)
    notebook = json.loads(target.read_text())
    bootstrap = next(c for c in notebook["cells"] if c["metadata"]["id"] == "rda-frozen-engine")
    import ast, hashlib
    tree = ast.parse("".join(bootstrap["source"]))
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"BUNDLE", "MANIFEST"}}
    decoded = json.loads(zlib.decompress(base64.b64decode(values["BUNDLE"])))
    for name in ("creative_pipeline.py", "gemini_gateway.py", "product_generation.py"):
        raw = base64.b64decode(decoded[name])
        assert raw == source_at(name)
        assert hashlib.sha256(raw).hexdigest() == values["MANIFEST"][name]
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            ast.parse("".join(cell["source"]))
    legacy = next(c for c in notebook["cells"] if c["metadata"]["id"] == "2TLApgi7qMS4")
    assert "EJECUTAR_COMPRESION_HISTORICA = False" in "".join(legacy["source"])
