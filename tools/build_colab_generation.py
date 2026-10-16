"""Adjust only the image/prompts section of the user's original bulk Colab."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "4e04b738a5f228ed3a56c50c4d891625f76c9e48"


def source_at(path):
    return subprocess.check_output(["git", "show", SOURCE_COMMIT + ":" + path], cwd=ROOT).decode()


def extract(source, names):
    selected = []
    for node in ast.parse(source).body:
        if getattr(node, "name", None) in names or isinstance(node, ast.Assign) and any(getattr(n, "id", None) in names for n in node.targets):
            selected.append(ast.get_source_segment(source, node))
    return "\n\n".join(selected) + "\n"


REPLACEMENTS = '''
def obtener_cliente():
    """La misma clave del Colab; una llamada por intento como en la app."""
    global client
    if client is None:
        if genai is None:
            raise RuntimeError("Instala google-genai antes de generar.")
        client = genai.Client(api_key=obtener_api_key(), http_options=types.HttpOptions(
            timeout=120000, retry_options=types.HttpRetryOptions(attempts=1)))
    return client


def investigar_lifestyle(producto, desc, marca="", categoria="", subcategoria=""):
    return _plan_creativo(producto, marca, desc, categoria, subcategoria)["lifestyle"]


def investigar_comercial(producto, marca, desc, categoria="", subcategoria=""):
    return _plan_creativo(producto, marca, desc, categoria, subcategoria)["comercial"]


def generar_imagen(prompt, ruta_imagen_local, ruta_salida):
    """Mismo flujo masivo: conserva existentes y guarda el JPG con su nombre original."""
    if imagen_ya_existe(ruta_salida):
        print(f"⏭️ Ya existe, no se modifica: {os.path.basename(ruta_salida)}")
        return "existente"
    filename = os.path.basename(ruta_salida)
    slot = "2_uso" if filename.endswith("_2_uso.jpg") else "3_comercial" if filename.endswith("_3_comercial.jpg") else "1_hd"
    temporal = None
    try:
        picture = generate(obtener_cliente(), [ruta_imagen_local], prompt, slot,
                           styles=_estilos_comerciales() if slot == "3_comercial" else ())
        with tempfile.NamedTemporaryFile(suffix=".jpg", dir=os.path.dirname(ruta_salida) or ".", delete=False) as file:
            temporal = file.name
        picture.save(temporal, "JPEG", quality=94, optimize=True)
        estampar_logo(temporal)
        os.replace(temporal, ruta_salida)
        print(f"✅ Lista: {filename}")
        time.sleep(2)
        return "generada"
    except Exception as exc:
        print(f"❌ {filename}: {type(exc).__name__}. Revisa cuota, permisos y la referencia; el lote continúa.")
        return "fallida"
    finally:
        if temporal and os.path.exists(temporal):
            os.remove(temporal)
'''

HELPERS = '''
# Prompts y utilidades de generación de la app, visibles en esta misma celda.
import hashlib
import io
import json
from pathlib import Path
import threading
from urllib.parse import urlparse
from google.genai import types
from PIL import ImageOps

_PLANES_CREATIVOS = {}
_ESTILOS = None
_CREATIVE_LOCK = threading.RLock()


def _estilos_comerciales():
    """Hasta dos ejemplos comerciales de la misma carpeta de Drive del Colab."""
    global _ESTILOS
    with _CREATIVE_LOCK:
        if _ESTILOS and time.monotonic() - _ESTILOS[0] < 600 and all(Path(p).is_file() for p in _ESTILOS[1]):
            return _ESTILOS[1]
        folder = Path(OUTPUT_DIR)
        candidates = [p for p in folder.glob("*") if p.is_file() and re.search(r"_3(?:_comercial)?\\.(?:png|jpe?g)$", p.name, re.I)]
        candidates.sort(key=lambda p: (0 if re.search(r"_3\\.png$", p.name, re.I) else 1, -p.stat().st_mtime_ns))
        paths = []
        for candidate in candidates:
            if len(paths) == 2:
                break
            if candidate.stat().st_size > 12_000_000:
                continue
            try:
                with Image.open(candidate) as source:
                    picture = ImageOps.exif_transpose(source).convert("RGB")
                    picture.thumbnail((900, 900))
                    digest = hashlib.sha256((str(candidate) + str(candidate.stat().st_mtime_ns)).encode()).hexdigest()[:20]
                    target = Path(TEMP_DIR) / ("_estilo_" + digest + ".jpg")
                    if not target.exists():
                        picture.save(target, "JPEG", quality=82, optimize=True)
                paths.append(str(target))
            except (OSError, ValueError):
                continue
        _ESTILOS = (time.monotonic(), paths)
        return paths


def _plan_creativo(producto, marca, desc, categoria="", subcategoria=""):
    data = {"name": producto, "brand": marca, "description": desc,
            "category": categoria, "subcategory": subcategoria}
    styles = _estilos_comerciales()
    key = plan_key(data, styles)
    with _CREATIVE_LOCK:
        if key in _PLANES_CREATIVOS:
            return _PLANES_CREATIVOS[key]
    try:
        result = brief(obtener_cliente(), data, styles)
    except Exception:
        result = fallback_brief(data, "La investigación no estuvo disponible; se usará una escena original.")
    with _CREATIVE_LOCK:
        if len(_PLANES_CREATIVOS) >= 256:
            _PLANES_CREATIVOS.pop(next(iter(_PLANES_CREATIVOS)))
        _PLANES_CREATIVOS[key] = result
    return result
'''


def adapted_source(original):
    tree = ast.parse(original)
    replacements = {n.name: ast.get_source_segment(REPLACEMENTS, n) for n in ast.parse(REPLACEMENTS).body if isinstance(n, ast.FunctionDef)}
    edits = []
    lines = original.splitlines(True)
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in replacements:
            edits.append((node.lineno - 1, node.end_lineno, replacements[node.name] + "\n"))
        elif node.name == "procesar_producto":
            method = "".join(lines[node.lineno - 1:node.end_lineno])
            parsed = ast.parse(method).body[0]
            hd = next(n for n in ast.walk(parsed) if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "prompt_hd" for t in n.targets))
            method = method.replace(ast.get_source_segment(method, hd), "prompt_hd = PROMPT_HD", 1)
            context = 'categoria=texto_celda(row, "categorias") or texto_celda(row, "categoria"), subcategoria=texto_celda(row, "subcategoria")'
            method = method.replace("investigar_lifestyle(producto, desc)", "investigar_lifestyle(producto, desc, marca=marca, " + context + ")")
            method = method.replace("investigar_comercial(producto, marca, desc)", "investigar_comercial(producto, marca, desc, " + context + ")")
            method = method.replace('prompt_uso_final = f"{prompt_uso} {regla_sin_empaques}"', 'prompt_uso_final = prompt_uso')
            method = method.replace('prompt_comercial_final = f"{prompt_comercial} {regla_sin_empaques}"', 'prompt_comercial_final = prompt_comercial')
            edits.append((node.lineno - 1, node.end_lineno, method))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]
    source = "".join(lines)
    gateway = extract(source_at("gemini_gateway.py"), {"text_config", "image_part", "parse_json"})
    creative = extract(source_at("creative_pipeline.py"), {"SLOTS", "TEXT_MODEL", "IMAGE_MODEL", "FIDELITY", "product_data", "interaction_for", "fallback_brief", "grounding", "brief", "plan_key", "image_config", "image_contents", "extract_image", "generate"})
    hd = extract(source_at("app.py"), {"PROMPT_HD"})
    insertion = HELPERS + "\n" + gateway + "\n" + creative + "\n" + hd + "\n"
    source = source.replace("# 1. CONFIGURACIÓN\n", insertion + "# 1. CONFIGURACIÓN\n", 1)
    ast.parse(source)
    return source


def build(original_path, destination):
    notebook = json.loads(Path(original_path).read_text())
    updated = deepcopy(notebook)
    cell = next(c for c in updated["cells"] if c.get("metadata", {}).get("id") == "-vY-eouWVDOt")
    cell["source"] = adapted_source("".join(cell["source"])).splitlines(True)
    cell["outputs"] = []
    cell["execution_count"] = None
    Path(destination).write_text(json.dumps(updated, ensure_ascii=False, indent=1) + "\n")
    (ROOT / "colab/generation_backup.py").write_text("".join(cell["source"]))
    print(json.dumps({"cells": len(updated["cells"]), "modified_cell": "-vY-eouWVDOt", "preserved_other_cells": len(updated["cells"]) - 1}))


if __name__ == "__main__":
    build(*sys.argv[1:3])
