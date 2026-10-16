"""Original bulk Colab behavior, with only app prompts/image methods adapted."""
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest

from tools.build_colab_generation import source_at


UNCHANGED = {
    "obtener_api_key": "91899f1d8402ba653061f1d2296fb084a0d798220c60f779538b6a9c80c8e9cc",
    "validar_dependencias_generacion": "2a5930a69a6c99ab891ec2469272d0a64f49a233d6fc5a3312ff3b4773628cde",
    "ruta_absoluta": "670dc7513d85b821a55d2f9ef63a5e7ca96ee2b31e7786c083166b059cf92ed5",
    "carpeta_predeterminada": "1d2b049cd37ade191fa79500ac4017b3791187d159ea53e8c9fe5ad16e9c3a85",
    "crear_argumentos": "7a41630905b866ee6a19b40382fee3e7690d1d92ce7490a7a14d612bdf9ee92c",
    "configurar_rutas": "1ee4ef10251f8ac01f5ad9f626d672fd8e7ff5bd6a81b91a2841e7f259387eac",
    "clave_encabezado": "d4f2ea70aaf8ff74823234a536de1f0d727e958d05d5bb697459cc4b816be739",
    "limpiar_columnas": "73c5465b09b7dcd8a839bfce192e64d53d7494cc0bbecbe865991e3b8fc03b45",
    "leer_inventario": "7068fa90e3a2936b6c9af93c9ba01ccb7e8670e6a2e4314431f57297e5eea312",
    "estampar_logo": "72367f6c91a7e0b4cd800be14f3f2ad819446d087b905616769087811f9172db",
    "texto_celda": "562ba8929c18e3638ca0357e698905ce809a5cf2595d67b6892447c5bf0f9ff8",
    "extraer_url_imagen": "3c465f406e2323e0d0876ea1191c9f77f05fd65cf6324e8903d52430202a63f2",
    "extension_imagen": "e537c75f5b265d7542a2c3d10d17079bc7f04781efb542125efd3de1db39f658",
    "descargar_imagen_referencia": "7e48943961d07b9e6fc2ce407fc1bc139856a5be1b0a832ab9c53797cac9f3a5",
    "rutas_imagenes_producto": "e96a5f4f0ba2d91b98ab26104461b1881e1ce4d974921b0e783bb47784ccd5c9",
    "imagen_ya_existe": "c346295e93c8505c178c7c4fbc00872232a9b63db80166ddfe9c6729c3617f34",
    "auditar_imagenes": "92010d916d0034b411336c0579d62dac09c164a70d98819a3f55497d4838e327",
    "main": "d95891a9e6cbd81c91033995a9a736128cd80211e3abda1a3b3b5d5972bddb3f",
}


def test_original_csv_drive_logo_audit_and_bulk_methods_are_unchanged():
    tree = ast.parse(Path("colab/generation_backup.py").read_text())
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name, expected in UNCHANGED.items():
        assert hashlib.sha256(ast.dump(nodes[name], include_attributes=False).encode()).hexdigest() == expected, name


def test_inline_prompts_and_pure_image_functions_match_the_app():
    tree = ast.parse(Path("colab/generation_backup.py").read_text())
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for filename, names in {
        "creative_pipeline.py": ["brief", "fallback_brief", "interaction_for", "image_contents", "generate", "image_config", "extract_image"],
        "gemini_gateway.py": ["image_part", "text_config", "parse_json"],
    }.items():
        source = {n.name: n for n in ast.parse(source_at(filename)).body if isinstance(n, ast.FunctionDef)}
        for name in names:
            assert ast.dump(nodes[name], include_attributes=False) == ast.dump(source[name], include_attributes=False), name


class FakeGemini:
    def __init__(self):
        self.models = self
        self.calls = []
        self.fail_once = False

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["model"] == "gemini-2.5-flash":
            return SimpleNamespace(text=json.dumps({"lifestyle": "An adult naturally tasting the exact food with the real package beside the person.",
                "comercial": "An artistic advertising hero shot with bold expressive illustration around the unchanged original package.",
                "ads_found": False, "note": "Original"}), candidates=[])
        if self.fail_once:
            self.fail_once = False
            raise TimeoutError("private-key")
        picture = Image.new("RGB", (1024, 1024), "purple")
        ImageDraw.Draw(picture).rectangle((250, 200, 750, 850), fill="orange")
        stream = io.BytesIO()
        picture.save(stream, "PNG")
        part = SimpleNamespace(thought=False, inline_data=SimpleNamespace(mime_type="image/png", data=stream.getvalue()))
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


@pytest.fixture
def bulk(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("original_bulk_colab", Path("colab/generation_backup.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = FakeGemini()
    module.client = fake
    monkeypatch.setattr(module.time, "sleep", lambda *args: None)
    Image.new("RGBA", (100, 80), (255, 0, 0, 160)).save(tmp_path / "logo_rincon_asia.png")
    reference = tmp_path / "reference.png"
    Image.new("RGB", (300, 400), "blue").save(reference)
    (tmp_path / "inventario_completo.csv").write_text("sku,nombre_producto,Marca,Web link imagen\nPOCK,Pocky,Glico,https://example.test/reference.png\n")
    def download(url, sku):
        target = tmp_path / "download.png"
        shutil.copy2(reference, target)
        return str(target)
    monkeypatch.setattr(module, "descargar_imagen_referencia", download)
    return module, fake, tmp_path


def test_original_audit_does_not_call_gemini(bulk):
    module, fake, folder = bulk
    assert module.main(["--base-dir", str(folder), "--solo-auditoria"]) == 0
    assert fake.calls == [] and (folder / "faltantes.csv").is_file()


def test_original_batch_generates_directly_into_drive_and_skips_existing_files(bulk):
    module, fake, folder = bulk
    assert module.main(["--base-dir", str(folder), "--workers", "4"]) == 0
    files = sorted((folder / "imagenes_generadas").glob("*.jpg"))
    assert {p.name for p in files} == {"POCK_1_hd.jpg", "POCK_2_uso.jpg", "POCK_3_comercial.jpg"}
    assert len(fake.calls) == 4  # One shared creative brief, three image requests.
    image_calls = [call for call in fake.calls if call["model"] == "gemini-3.1-flash-image"]
    assert module.PROMPT_HD in image_calls[0]["contents"][-1]
    assert all(module.FIDELITY in call["contents"][-1] for call in image_calls)
    assert all(call["config"].image_config.aspect_ratio == "1:1" for call in image_calls)
    before = {p.name: p.read_bytes() for p in files}
    assert module.main(["--base-dir", str(folder)]) == 0
    assert len(fake.calls) == 4 and before == {p.name: p.read_bytes() for p in files}
    assert not (folder / "colab_respaldo_generacion").exists()


def test_failed_image_does_not_block_the_other_original_slots(bulk):
    module, fake, folder = bulk
    fake.fail_once = True
    assert module.main(["--base-dir", str(folder)]) == 2
    output = folder / "imagenes_generadas"
    assert not (output / "POCK_1_hd.jpg").exists()
    assert (output / "POCK_2_uso.jpg").is_file() and (output / "POCK_3_comercial.jpg").is_file()
    assert len([call for call in fake.calls if call["model"] == "gemini-3.1-flash-image"]) == 3


def test_shared_creative_plan_uses_two_style_examples_from_the_original_folder(bulk):
    module, fake, folder = bulk
    output = folder / "imagenes_generadas"
    output.mkdir()
    temporary = folder / "imagenes_temporales"
    temporary.mkdir()
    for name in ("original_3.png", "new_3_comercial.jpg"):
        Image.new("RGB", (1200, 1200), "orange").save(output / name)
    module.OUTPUT_DIR, module.TEMP_DIR = str(output), str(temporary)
    module.investigar_lifestyle("Pocky", "Galleta", marca="Glico")
    module.investigar_comercial("Pocky", "Glico", "Galleta")
    assert len(fake.calls) == 1
    assert len(module._estilos_comerciales()) == 2
    assert len([part for part in fake.calls[0]["contents"] if isinstance(part, str) and part.startswith("STYLE EXAMPLE")]) == 2
